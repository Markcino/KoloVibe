import 'package:flutter/services.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/feature_repository.dart';
import '../../core/security/credential_store.dart';
import 'account_repository.dart';

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
        id, DateTime.parse(created), DateTime.parse(expires), current);
  }
}

class LiveAccountRepository implements AccountRepository {
  LiveAccountRepository(this.api, this.store);
  final ApiClient api;
  final CredentialStore store;
  String? _accessToken;
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
    _accessToken = access;
  }

  Future<LiveAccount?> currentAccount() => _serialized(_currentAccount);

  Future<bool> _refresh() async {
    final refresh = await store.readRefreshToken();
    if (refresh == null) return false;
    await _accept(await api.request('/auth/refresh',
        method: 'POST', body: {'refresh_token': refresh}));
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

  Future<Map<String, dynamic>> _sessionRequest(String path,
      {String method = 'GET'}) async {
    const expired = ApiFailure(401, 'Sign in again to manage sessions.');
    try {
      final restored = _accessToken == null;
      if (restored && !await _refresh()) throw expired;
      try {
        return await api.request(path,
            method: method, accessToken: _accessToken);
      } on ApiFailure catch (error) {
        if (error.status != 401 || restored) rethrow;
        if (!await _refresh()) throw expired;
        return await api.request(path,
            method: method, accessToken: _accessToken);
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

  @override
  Future<UiResult> execute(UiRequest request) =>
      _serialized(() => _execute(request));

  Future<UiResult> _execute(UiRequest request) async {
    try {
      final fields = request.fields;
      switch (request.operation) {
        case UiOperation.register:
          await api.request('/auth/register', method: 'POST', body: {
            'email': fields['Email address'] ?? '',
            'password': fields['Password'] ?? '',
            'display_name': fields['Full name'] ?? fields['Display name'] ?? '',
          });
          return const UiResult.success(
              message: 'Check your email for a verification code.');
        case UiOperation.requestCode:
          await api.request('/auth/verification/resend', method: 'POST', body: {
            'email': fields['Email address'] ?? '',
          });
          return const UiResult.success(
              message: 'If eligible, you will receive a new code by email.');
        case UiOperation.verifyEmail:
          await api.request('/auth/verify',
              method: 'POST', body: {'code': fields['verificationCode'] ?? ''});
          return const UiResult.success(
              message: 'Email verified. You can sign in.');
        case UiOperation.signIn:
          await _accept(await api.request('/auth/login', method: 'POST', body: {
            'email': fields['Email address'] ?? '',
            'password': fields['Password'] ?? '',
          }));
          return const UiResult.success(message: 'Signed in.');
        case UiOperation.signOut:
          final refresh = await store.readRefreshToken();
          var revocationConfirmed = true;
          if (refresh != null) {
            try {
              await api.request('/auth/logout',
                  method: 'POST', body: {'refresh_token': refresh});
            } on ApiFailure {
              revocationConfirmed = false;
            }
          }
          _accessToken = null;
          await store.clearRefreshToken();
          if (!revocationConfirmed) {
            return const UiResult.failure(
                'Signed out on this device. Server session revocation could not be confirmed.');
          }
          return const UiResult.success(message: 'Signed out.');
        default:
          return const UiResult.unavailable();
      }
    } on ApiFailure catch (error) {
      return UiResult.failure(error.message);
    } on PlatformException {
      return const UiResult.failure(
          'Secure credential storage is unavailable.');
    } on FormatException {
      return const UiResult.failure(
          'The service returned an invalid response.');
    }
  }
}
