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
      final restored = _accessToken == null;
      if (restored && !await _refresh()) return null;
      try {
        return LiveAccount.fromJson(
            await api.request('/me', accessToken: _accessToken));
      } on ApiFailure catch (error) {
        if (error.status != 401 || restored) rethrow;
        if (!await _refresh()) {
          _accessToken = null;
          return null;
        }
        return LiveAccount.fromJson(
            await api.request('/me', accessToken: _accessToken));
      }
    } on ApiFailure catch (error) {
      if (error.status == 401) {
        _accessToken = null;
        await store.clearRefreshToken();
        return null;
      }
      rethrow;
    }
  }

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
