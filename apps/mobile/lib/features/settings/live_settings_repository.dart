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
}
