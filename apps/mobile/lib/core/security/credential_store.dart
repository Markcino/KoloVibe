import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract interface class CredentialStore {
  Future<String?> readRefreshToken();
  Future<void> writeRefreshToken(String token);
  Future<void> clearRefreshToken();
}

class PlatformCredentialStore implements CredentialStore {
  const PlatformCredentialStore();
  static const _storage = FlutterSecureStorage();
  static const _key = 'kolovibe.refresh.v1';

  @override
  Future<String?> readRefreshToken() => _storage.read(key: _key);

  @override
  Future<void> writeRefreshToken(String token) =>
      _storage.write(key: _key, value: token);

  @override
  Future<void> clearRefreshToken() => _storage.delete(key: _key);
}
