import 'package:flutter/services.dart';

import '../../core/network/api_client.dart';
import '../../core/presentation/feature_repository.dart';
import '../../core/security/credential_store.dart';
import 'account_repository.dart';

/// Ephemeral account/session-bound proof. Never persist in route arguments or storage.
/// Taking the proof clears this object's token even if delivery subsequently fails.
class Reauthentication {
  Reauthentication(String token, this.expiresAt) : _token = token;
  String? _token;
  final DateTime expiresAt;
  bool get available => _token != null && DateTime.now().isBefore(expiresAt);

  factory Reauthentication.fromJson(Map<String, dynamic> data) {
    final token = data['reauth_token'], expires = data['expires_at'];
    if (data.length != 2 ||
        token is! String ||
        !RegExp(r'^[A-Za-z0-9_-]{32,128}$').hasMatch(token) ||
        expires is! String ||
        !RegExp(r'(Z|[+-]\d\d:\d\d)$').hasMatch(expires)) {
      throw const FormatException('Invalid identity verification response');
    }
    final stamp = DateTime.tryParse(expires);
    if (stamp == null || !stamp.isAfter(DateTime.now())) {
      throw const FormatException('Expired identity verification response');
    }
    return Reauthentication(token, stamp);
  }

  String take() {
    final valid = available;
    final value = _token;
    _token = null;
    if (!valid || value == null) {
      throw const ApiFailure(400, 'Confirm your identity again to continue.');
    }
    return value;
  }

  void dispose() => _token = null;
}

/// Decision G: a single-use proof from Identity for one named purpose (and resource). Held only in memory for the
/// one request it was obtained for; taking it clears it, so a retry needs a fresh confirmation.
class StepUpProof {
  StepUpProof(String token, this.purpose, this.expiresAt) : _token = token;
  String? _token;
  final String purpose;
  final DateTime expiresAt;

  factory StepUpProof.fromJson(Map<String, dynamic> data, String purpose) {
    final token = data['step_up_token'], expires = data['expires_at'];
    if (data.length != 3 ||
        data['purpose'] != purpose ||
        token is! String ||
        !RegExp(r'^[A-Za-z0-9_-]{32,128}$').hasMatch(token) ||
        expires is! String ||
        !RegExp(r'(Z|[+-]\d\d:\d\d)$').hasMatch(expires)) {
      throw const FormatException('Invalid security check response');
    }
    final stamp = DateTime.tryParse(expires);
    if (stamp == null || !stamp.isAfter(DateTime.now())) {
      throw const FormatException('Expired security check response');
    }
    return StepUpProof(token, purpose, stamp);
  }

  String take() {
    final value = _token;
    _token = null;
    if (value == null || !DateTime.now().isBefore(expiresAt)) {
      throw const ApiFailure(403, 'Confirm your password again to continue.');
    }
    return value;
  }
}

class LiveAccount {
  const LiveAccount(this.id, this.email, this.displayName, this.roles);
  final String id, email, displayName;
  final List<String> roles;

  factory LiveAccount.fromJson(Map<String, dynamic> data) {
    final id = data['id'], email = data['email'], name = data['display_name'];
    final roles = data['roles'];
    if (id is! String ||
        email is! String ||
        name is! String ||
        roles is! List ||
        roles.any((role) => role is! String)) {
      throw const FormatException('Invalid account');
    }
    return LiveAccount(id, email, name, roles.cast<String>());
  }
}

class AccountSession {
  const AccountSession(this.id, this.createdAt, this.expiresAt, this.current);

  final String id;
  final DateTime createdAt, expiresAt;
  final bool current;

  factory AccountSession.fromJson(Object? value) {
    if (value is! Map<String, dynamic>) {
      throw const FormatException('Invalid session');
    }
    final id = value['id'];
    final created = value['created_at'];
    final expires = value['expires_at'];
    final current = value['current'];
    if (id is! String ||
        !isApiId(id) ||
        created is! String ||
        expires is! String ||
        current is! bool) {
      throw const FormatException('Invalid session');
    }
    return AccountSession(
      id,
      DateTime.parse(created),
      DateTime.parse(expires),
      current,
    );
  }
}

class LiveAccountRepository implements AccountRepository {
  LiveAccountRepository(this.api, this.store);
  final ApiClient api;
  final CredentialStore store;
  String? _accessToken;

  /// Called whenever this device's session ends, even when the server could not confirm it, so
  /// device-local personal data (recent searches) never outlives the signed-in person.
  Future<void> Function()? onSessionEnded;
  String? _accountId;

  /// Id of the account holding the current session, from the last token response; null when
  /// signed out. Used only to keep device-local data apart per account.
  String? get signedInAccountId => _accessToken == null ? null : _accountId;
  Future<void> _pending = Future<void>.value();

  Future<T> _serialized<T>(Future<T> Function() action) {
    final result = _pending.then((_) => action());
    // A failed request must not prevent subsequent session operations.
    _pending = result.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return result;
  }

  Future<void> _accept(Map<String, dynamic> response) async {
    final access = response['access_token'],
        refresh = response['refresh_token'];
    if (access is! String ||
        refresh is! String ||
        access.isEmpty ||
        refresh.isEmpty) {
      throw const ApiFailure(503, 'The sign-in response was invalid.');
    }
    await store.writeRefreshToken(refresh);
    _restored = null;
    _accessToken = access;
    final user = response['user'];
    final id = user is Map ? user['id'] : null;
    _accountId = id is String && isApiId(id) ? id : null;
  }

  Future<void> _sessionEnded() async {
    _accountId = null;
    try {
      await onSessionEnded?.call();
    } catch (_) {
      // Failing to tidy local data must not block sign-out.
    }
  }

  Future<LiveAccount?> currentAccount() => _serialized(_currentAccount);

  /// A missing credential is a fresh start; a rejected saved session is M-101.
  Future<LiveAccount?> restoreSession() => _serialized(() async {
        if (_accessToken == null && await store.readRefreshToken() == null) {
          return null;
        }
        final account = LiveAccount.fromJson(await _sessionRequest('/me'));
        _restored = account;
        return account;
      });

  LiveAccount? _restored;

  /// The account read by [restoreSession], handed over once so the first
  /// screen after startup does not repeat the request. Later calls, and any
  /// call after the session ended, return null and callers read /me instead.
  LiveAccount? takeRestoredAccount() {
    final account = _restored;
    _restored = null;
    return account;
  }

  Future<bool> _refresh() async {
    final refresh = await store.readRefreshToken();
    if (refresh == null) return false;
    await _accept(
      await api.request(
        '/auth/refresh',
        method: 'POST',
        body: {'refresh_token': refresh},
      ),
    );
    return true;
  }

  Future<LiveAccount?> _currentAccount() async {
    try {
      return LiveAccount.fromJson(await _sessionRequest('/me'));
    } on ApiFailure catch (error) {
      if (error.status == 401) return null;
      rethrow;
    }
  }

  Future<Map<String, dynamic>> _sessionRequest(
    String path, {
    String method = 'GET',
    Map<String, String>? query,
    Map<String, Object?>? body,
    String? idempotencyKey,
    String? stepUpToken,
  }) async {
    const expired = ApiFailure(401, 'Sign in again to manage sessions.');
    try {
      final restored = _accessToken == null;
      if (restored && !await _refresh()) throw expired;
      try {
        return await api.request(
          path,
          method: method,
          accessToken: _accessToken,
          query: query,
          body: body,
          idempotencyKey: idempotencyKey,
          stepUpToken: stepUpToken,
        );
      } on ApiFailure catch (error) {
        if (error.status != 401 || restored) rethrow;
        if (!await _refresh()) throw expired;
        return await api.request(
          path,
          method: method,
          accessToken: _accessToken,
          query: query,
          body: body,
          idempotencyKey: idempotencyKey,
          stepUpToken: stepUpToken,
        );
      }
    } on ApiFailure catch (error) {
      if (error.status != 401) rethrow;
      _accessToken = null;
      await store.clearRefreshToken();
      throw expired;
    }
  }

  Future<List<AccountSession>> sessions() => _serialized(() async {
        final result = await _sessionRequest('/me/sessions');
        final items = result['items'];
        if (items is! List || items.length > 40) {
          throw const FormatException('Invalid session list');
        }
        return items.map(AccountSession.fromJson).toList(growable: false);
      });

  Future<void> revokeSession(String id) => _serialized(() async {
        if (!isApiId(id)) {
          throw const FormatException('Invalid session identifier');
        }
        await _sessionRequest('/me/sessions/$id', method: 'DELETE');
      });

  Future<Map<String, dynamic>> authenticatedRequest(
    String path, {
    String method = 'GET',
    Map<String, String>? query,
    Map<String, Object?>? body,
    String? idempotencyKey,
    String? stepUpToken,
  }) =>
      _serialized(
        () => _sessionRequest(
          path,
          method: method,
          query: query,
          body: body,
          idempotencyKey: idempotencyKey,
          stepUpToken: stepUpToken,
        ),
      );

  @override
  Future<UiResult> execute(UiRequest request) =>
      _serialized(() => _execute(request));

  /// Typed failures for live flows; the legacy execute adapter remains compatible.
  Future<UiResult> executeChecked(UiRequest request) =>
      _serialized(() => _perform(request));

  Future<Reauthentication> reauthenticate(String currentPassword) =>
      _serialized(() async {
        if (currentPassword.isEmpty || currentPassword.length > 128) {
          throw const ApiFailure(400, 'Enter your current password.');
        }
        return Reauthentication.fromJson(
          await _sessionRequest(
            '/me/reauthenticate',
            method: 'POST',
            body: {'current_password': currentPassword},
          ),
        );
      });

  /// Decision G: confirm the password to obtain a proof for one sensitive action on one resource.
  Future<StepUpProof> stepUp(String currentPassword, String purpose,
          {String? resourceId}) =>
      _serialized(() async {
        if (currentPassword.isEmpty || currentPassword.length > 128) {
          throw const ApiFailure(400, 'Enter your current password.');
        }
        if (!RegExp(r'^[a-z]+\.[a-z_]{1,48}$').hasMatch(purpose) ||
            (resourceId != null && !isApiId(resourceId))) {
          throw ArgumentError('Invalid security check');
        }
        final Map<String, dynamic> answer;
        try {
          answer = await _sessionRequest(
            '/me/step-up',
            method: 'POST',
            body: {
              'current_password': currentPassword,
              'purpose': purpose,
              if (resourceId != null) 'resource_id': resourceId,
            },
          );
        } on ApiFailure catch (error) {
          // Identity answers a wrong password with a bare 400; name it on this one route so the screen can say so.
          if (error.status == 400) {
            throw const ApiFailure(400, 'The password is not correct.',
                code: 'step_up_password');
          }
          rethrow;
        }
        return StepUpProof.fromJson(answer, purpose);
      });

  Future<void> clearSession() => _serialized(() async {
        _restored = null;
        _accessToken = null;
        await store.clearRefreshToken();
        await _sessionEnded();
      });

  Future<void> signOut() => _serialized(_signOut);

  Future<void> _signOut() async {
    try {
      final refresh = await store.readRefreshToken();
      if (refresh != null) {
        await api.request(
          '/auth/logout',
          method: 'POST',
          body: {'refresh_token': refresh},
        );
      }
    } finally {
      _restored = null;
      _accessToken = null;
      await store.clearRefreshToken();
      await _sessionEnded();
    }
  }

  Future<UiResult> _execute(UiRequest request) async {
    try {
      return await _perform(request);
    } on ApiFailure catch (error) {
      return UiResult.failure(error.message);
    } on PlatformException {
      return const UiResult.failure(
        'Secure credential storage is unavailable.',
      );
    } on FormatException {
      return const UiResult.failure(
        'The service returned an invalid response.',
      );
    }
  }

  Future<UiResult> _perform(UiRequest request) async {
    final fields = request.fields;
    switch (request.operation) {
      case UiOperation.register:
        await api.request(
          '/auth/register',
          method: 'POST',
          body: {
            'email': fields['Email address'] ?? '',
            'password': fields['Password'] ?? '',
            'display_name': fields['Full name'] ?? fields['Display name'] ?? '',
          },
        );
        return const UiResult.success(
          message: 'Check your email for a verification code.',
        );
      case UiOperation.requestCode:
        await api.request(
          '/auth/verification/resend',
          method: 'POST',
          body: {'email': fields['Email address'] ?? ''},
        );
        return const UiResult.success(
          message: 'If eligible, you will receive a new code by email.',
        );
      case UiOperation.verifyEmail:
        await api.request(
          '/auth/verify',
          method: 'POST',
          body: {
            'email': fields['Email address'] ?? '',
            'code': fields['verificationCode'] ?? '',
          },
        );
        return const UiResult.success(
          message: 'Email verified. You can sign in.',
        );
      case UiOperation.requestReset:
        await api.request(
          '/auth/password/reset-request',
          method: 'POST',
          body: {'email': fields['Email address'] ?? ''},
        );
        return const UiResult.success(
          message:
              'If the account is eligible, reset instructions will arrive by email.',
        );
      case UiOperation.resetPassword:
        final newPassword = fields['New password'] ?? '';
        if (fields.containsKey('Current password')) {
          await _sessionRequest(
            '/me/password',
            method: 'PATCH',
            body: {
              'current_password': fields['Current password'] ?? '',
              'new_password': newPassword,
            },
          );
          return const UiResult.success(
            message: 'Password updated. Other sessions have been signed out.',
          );
        }
        await api.request(
          '/auth/password/reset',
          method: 'POST',
          body: {
            'email': fields['Email address'] ?? '',
            'code': fields['Reset code'] ?? '',
            'new_password': newPassword,
          },
        );
        _accessToken = null;
        await store.clearRefreshToken();
        return const UiResult.success(
          message: 'Password updated. Sign in again.',
        );
      case UiOperation.saveProfile:
        await _sessionRequest(
          '/me',
          method: 'PATCH',
          body: {'display_name': fields['Display name'] ?? ''},
        );
        return const UiResult.success(message: 'Profile updated.');
      case UiOperation.signIn:
        final response = await api.request(
          '/auth/login',
          method: 'POST',
          body: {
            'email': fields['Email address'] ?? '',
            'password': fields['Password'] ?? '',
          },
        );
        if (response['mfa_required'] == true) {
          throw const ApiFailure(
            403,
            'This account requires an MFA sign-in flow.',
          );
        }
        await _accept(response);
        return const UiResult.success(message: 'Signed in.');
      case UiOperation.signOut:
        try {
          await _signOut();
          return const UiResult.success(message: 'Signed out.');
        } on ApiFailure {
          return const UiResult.failure(
            'Signed out on this device. Server session revocation could not be confirmed.',
          );
        }
      default:
        return const UiResult.unavailable();
    }
  }
}
