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
    if (id is! String || email is! String || name is! String ||
        roles is! List || roles.any((role) => role is! String)) {
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

  Future<void> _accept(Map<String, dynamic> response) async {
    final access = response['access_token'], refresh = response['refresh_token'];
    if (access is! String || refresh is! String || access.isEmpty || refresh.isEmpty) {
      throw const ApiFailure(503, 'The sign-in response was invalid.');
    }
    await store.writeRefreshToken(refresh);
    _accessToken = access;
  }

  Future<LiveAccount?> currentAccount() async {
    try {
      if (_accessToken == null) {
        final refresh = await store.readRefreshToken();
        if (refresh == null) return null;
        await _accept(await api.request('/auth/refresh', method: 'POST',
            body: {'refresh_token': refresh}));
      }
      final response = await api.request('/me', accessToken: _accessToken);
      return LiveAccount.fromJson(response);
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
  Future<UiResult> execute(UiRequest request) async {
    try {
      final fields = request.fields;
      switch (request.operation) {
        case UiOperation.register:
          await api.request('/auth/register', method: 'POST', body: {
            'email': fields['Email address'] ?? '',
            'password': fields['Password'] ?? '',
            'display_name': fields['Full name'] ?? fields['Display name'] ?? '',
          });
          return const UiResult.success(message: 'Check your email for a verification code.');
        case UiOperation.verifyEmail:
          await api.request('/auth/verify', method: 'POST',
              body: {'code': fields['verificationCode'] ?? ''});
          return const UiResult.success(message: 'Email verified. You can sign in.');
        case UiOperation.signIn:
          await _accept(await api.request('/auth/login', method: 'POST', body: {
            'email': fields['Email address'] ?? '', 'password': fields['Password'] ?? '',
          }));
          return const UiResult.success(message: 'Signed in.');
        case UiOperation.signOut:
          final refresh = await store.readRefreshToken();
          if (refresh != null) {
            try {
              await api.request('/auth/logout', method: 'POST',
                  body: {'refresh_token': refresh});
            } on ApiFailure {
              // Clear the device credential even when the service is unavailable.
            }
          }
          _accessToken = null;
          await store.clearRefreshToken();
          return const UiResult.success(message: 'Signed out.');
        default:
          return const UiResult.unavailable();
      }
    } on ApiFailure catch (error) {
      return UiResult.failure(error.message);
    } catch (_) {
      return const UiResult.failure('The request could not be completed.');
    }
  }
}
