import 'dart:convert';

import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

class NotificationChoices {
  const NotificationChoices(this.email, this.push);
  final bool email, push;

  factory NotificationChoices.fromJson(Map<String, dynamic> data) {
    final email = data['email_notifications'],
        push = data['push_notifications'];
    if (data.length != 2 || email is! bool || push is! bool) {
      throw const FormatException('Invalid notification preferences');
    }
    return NotificationChoices(email, push);
  }
}

class PrivacyReceipt {
  const PrivacyReceipt(
    this.id,
    this.kind,
    this.status,
    this.createdAt, {
    this.existing = false,
  });
  final String id, kind, status;
  final DateTime createdAt;
  final bool existing;

  factory PrivacyReceipt.fromJson(Object? value) {
    if (value is! Map<String, dynamic>) {
      throw const FormatException('Invalid privacy receipt');
    }
    final id = value['id'], kind = value['kind'];
    final status = value['status'], created = value['created_at'];
    if (value.length != 4 ||
        id is! String ||
        !isApiId(id) ||
        kind is! String ||
        !{'access', 'deletion'}.contains(kind) ||
        !{'received', 'in_review', 'processing', 'completed', 'declined'}
            .contains(status) ||
        created is! String ||
        !RegExp(r'(Z|[+-]\d\d:\d\d)$').hasMatch(created)) {
      throw const FormatException('Invalid privacy receipt');
    }
    return PrivacyReceipt(id, kind, status as String, DateTime.parse(created));
  }
}

/// One service's part of an access export: named categories of flat rows, and the categories it withheld pending a
/// decision or cut at the row limit (names only).
class ExportPart {
  const ExportPart(this.data, this.withheld, this.truncated);
  final Map<String, List<Map<String, Object?>>> data;
  final List<String> withheld, truncated;
}

/// Mandate 3.3: the account's own assembled export, held in memory only while it is shown.
class AccessExport {
  const AccessExport(
      this.requestId, this.generatedAt, this.expiresAt, this.services);
  final String requestId;
  final DateTime generatedAt, expiresAt;
  final Map<String, ExportPart> services;

  static const knownServices = {
    'identity',
    'engagement',
    'creators',
    'moderation',
    'content',
    'business',
  };
  static final _name = RegExp(r'^[a-z][a-z0-9_]{0,39}$');

  static bool _plain(Object? value) =>
      value == null || value is String || value is num || value is bool;

  static List<String> _names(Object? value) {
    if (value is! List ||
        value.length > 40 ||
        value.toSet().length != value.length ||
        value.any((name) => name is! String || !_name.hasMatch(name))) {
      throw const FormatException('Invalid export');
    }
    return value.cast<String>();
  }

  factory AccessExport.fromJson(Map<String, dynamic> value) {
    final id = value['request_id'], generated = value['generated_at'];
    final expires = value['expires_at'], services = value['services'];
    if (value.length != 4 ||
        id is! String ||
        !isApiId(id) ||
        generated is! String ||
        expires is! String ||
        services is! Map<String, dynamic> ||
        !services.containsKey('identity') ||
        !knownServices.containsAll(services.keys)) {
      throw const FormatException('Invalid export');
    }
    final parts = <String, ExportPart>{};
    services.forEach((service, part) {
      if (part is! Map<String, dynamic> ||
          part.length != 3 ||
          part['data'] is! Map<String, dynamic>) {
        throw const FormatException('Invalid export');
      }
      final data = <String, List<Map<String, Object?>>>{};
      (part['data'] as Map<String, dynamic>).forEach((name, rows) {
        if (!_name.hasMatch(name) || rows is! List) {
          throw const FormatException('Invalid export');
        }
        data[name] = [
          for (final row in rows)
            if (row is Map<String, dynamic> &&
                row.values
                    .every((v) => _plain(v) || v is List && v.every(_plain)))
              row
            else
              throw const FormatException('Invalid export'),
        ];
      });
      parts[service] =
          ExportPart(data, _names(part['withheld']), _names(part['truncated']));
    });
    return AccessExport(
        id, DateTime.parse(generated), DateTime.parse(expires), parts);
  }

  /// The whole export as indented JSON, for the person to copy.
  String toText() => const JsonEncoder.withIndent('  ').convert({
        'request_id': requestId,
        'generated_at': generatedAt.toUtc().toIso8601String(),
        'expires_at': expiresAt.toUtc().toIso8601String(),
        'services': {
          for (final entry in services.entries)
            entry.key: {
              'data': entry.value.data,
              'withheld': entry.value.withheld,
              'truncated': entry.value.truncated,
            },
        },
      });
}

class LiveSettingsRepository {
  const LiveSettingsRepository(this.account);
  final LiveAccountRepository account;

  Future<NotificationChoices> preferences() async =>
      NotificationChoices.fromJson(
        await account.authenticatedRequest('/me/preferences'),
      );

  Future<NotificationChoices> updatePreferences(
    NotificationChoices value,
  ) async =>
      NotificationChoices.fromJson(
        await account.authenticatedRequest(
          '/me/preferences',
          method: 'PATCH',
          body: {
            'email_notifications': value.email,
            'push_notifications': value.push,
          },
        ),
      );

  Future<List<PrivacyReceipt>> privacyRequests() async {
    final data = await account.authenticatedRequest('/me/privacy-requests');
    final items = data['items'];
    if (data.length != 1 || items is! List || items.length > 40) {
      throw const FormatException('Invalid privacy request list');
    }
    return items.map(PrivacyReceipt.fromJson).toList(growable: false);
  }

  Future<PrivacyReceipt> requestPrivacy(
    String kind,
    String currentPassword,
  ) async {
    if (!{'access', 'deletion'}.contains(kind) || currentPassword.isEmpty) {
      throw const FormatException('Invalid privacy request');
    }
    final proof = await account.reauthenticate(currentPassword);
    return requestPrivacyWithProof(kind, proof);
  }

  Future<PrivacyReceipt> requestPrivacyWithProof(
    String kind,
    Reauthentication proof,
  ) async {
    if (!{'access', 'deletion'}.contains(kind)) {
      proof.dispose();
      throw const FormatException('Invalid privacy request');
    }
    try {
      return PrivacyReceipt.fromJson(
        await account.authenticatedRequest(
          '/me/privacy-requests',
          method: 'POST',
          body: {'kind': kind, 'reauth_token': proof.take()},
        ),
      );
    } on ApiFailure catch (failure) {
      if (failure.status != 409 || failure.code != 'request_open') rethrow;
      final open = (await privacyRequests()).where(
        (item) =>
            item.kind == kind &&
            {'received', 'in_review', 'processing'}.contains(item.status),
      );
      if (open.isEmpty) rethrow;
      final item = open.first;
      return PrivacyReceipt(
        item.id,
        item.kind,
        item.status,
        item.createdAt,
        existing: true,
      );
    } finally {
      proof.dispose();
    }
  }

  /// The account's own completed access export, after a fresh identity check. The service refuses it with 404 for
  /// any other account, 409 `export_not_ready` and 410 `export_expired`.
  Future<AccessExport> downloadExport(
    String requestId,
    Reauthentication proof,
  ) async {
    try {
      if (!isApiId(requestId)) {
        throw const FormatException('Invalid privacy request');
      }
      return AccessExport.fromJson(
        await account.authenticatedRequest(
          '/me/privacy-requests/$requestId/export',
          method: 'POST',
          body: {'reauth_token': proof.take()},
          maxBytes: exportMaxBytes,
        ),
      );
    } finally {
      proof.dispose();
    }
  }

  /// A transport bound that matches the gateway's, not a policy value.
  static const exportMaxBytes = 16 * 1024 * 1024;
}
