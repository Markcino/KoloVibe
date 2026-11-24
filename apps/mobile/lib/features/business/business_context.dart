import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../core/network/api_client.dart' show isApiId;

abstract interface class BusinessContextStore {
  Future<String?> read();
  Future<void> write(String value);
  Future<void> delete();
}

class SecureBusinessContextStore implements BusinessContextStore {
  const SecureBusinessContextStore();
  static const _storage = FlutterSecureStorage();
  static const _key = 'kolovibe.business.context.v1';
  @override
  Future<String?> read() => _storage.read(key: _key);
  @override
  Future<void> write(String value) => _storage.write(key: _key, value: value);
  @override
  Future<void> delete() => _storage.delete(key: _key);
}

class MemoryBusinessContextStore implements BusinessContextStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String value) async => this.value = value;
  @override
  Future<void> delete() async => value = null;
}

/// Which of the signed-in person's businesses the screens are working in.
///
/// This is a convenience, never authority: it holds one business id for one account, on this device only, and is
/// cleared on sign-out. Every request still names the business in its path and the service decides, on that request,
/// whether the person is a member and in what role. An id that is no longer theirs simply fails there.
class BusinessContext extends ChangeNotifier {
  BusinessContext(this.store);
  final BusinessContextStore store;
  String? _accountId;
  String? _businessId;

  String? get businessId => _businessId;

  /// The remembered business for [accountId], or null when nothing is remembered for that account.
  Future<String?> restore(String accountId) async {
    try {
      final raw = await store.read();
      if (raw != null) {
        final data = jsonDecode(raw);
        if (data is Map<String, dynamic> &&
            data.length == 2 &&
            data['account'] == accountId &&
            isApiId(data['business'])) {
          _accountId = accountId;
          _businessId = data['business'] as String;
          return _businessId;
        }
      }
    } on FormatException {
      // A damaged value is the same as no value.
    }
    _accountId = _businessId = null;
    return null;
  }

  Future<void> select(String accountId, String businessId) async {
    if (accountId.isEmpty || accountId.length > 64 || !isApiId(businessId)) {
      throw ArgumentError('Invalid business context');
    }
    _accountId = accountId;
    _businessId = businessId;
    await store
        .write(jsonEncode({'account': accountId, 'business': businessId}));
    notifyListeners();
  }

  /// Forget the choice, for example when the service says the person no longer has access.
  Future<void> clear() async {
    _accountId = _businessId = null;
    await store.delete();
    notifyListeners();
  }

  @visibleForTesting
  String? get accountId => _accountId;
}
