import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../../core/network/api_client.dart' show isApiId;

/// Device-local recent searches (D-5, M-021). The rules are specified in
/// `docs/privacy/recent-searches.md`: per signed-in account, at most [maxEntries],
/// each kept [retention] after it was last searched, never sent anywhere, cleared on sign-out.
abstract interface class SearchHistoryStore {
  Future<String?> read();
  Future<void> write(String value);
  Future<void> delete();
}

class SecureSearchHistoryStore implements SearchHistoryStore {
  const SecureSearchHistoryStore();
  static const _storage = FlutterSecureStorage();
  static const _key = 'kolovibe.search.v1';

  @override
  Future<String?> read() => _storage.read(key: _key);
  @override
  Future<void> write(String value) => _storage.write(key: _key, value: value);
  @override
  Future<void> delete() => _storage.delete(key: _key);
}

class MemorySearchHistoryStore implements SearchHistoryStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String value) async => this.value = value;
  @override
  Future<void> delete() async => value = null;
}

class SearchHistory {
  SearchHistory(this.store, {DateTime Function()? clock})
      : _now = clock ?? DateTime.now;
  static const maxEntries = 8;
  static const retention = Duration(days: 14);
  static const maxLength = 100;
  final SearchHistoryStore store;
  final DateTime Function() _now;
  Future<void> _queue = Future<void>.value();

  Future<T> _serialized<T>(Future<T> Function() action) {
    final result = _queue.then((_) => action());
    _queue = result.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return result;
  }

  /// What the person typed, or null when it must not be kept: blank, too long, or containing
  /// control characters.
  static String? clean(String raw) {
    final term = raw.trim();
    if (term.isEmpty ||
        term.length > maxLength ||
        term.codeUnits.any((c) => c < 32 || c == 127)) {
      return null;
    }
    return term;
  }

  static String _same(String term) =>
      term.toLowerCase().split(RegExp(r'\s+')).join(' ');

  Map<String, List<_Entry>> _decode(String? raw) {
    final result = <String, List<_Entry>>{};
    if (raw == null) return result;
    final cutoff = _now().subtract(retention);
    final latest = _now().add(const Duration(days: 1));
    try {
      final data = jsonDecode(raw);
      if (data is! Map || data['v'] != 1 || data['accounts'] is! Map) {
        return result;
      }
      for (final account in (data['accounts'] as Map).entries) {
        if (account.key is! String ||
            !isApiId(account.key as String) ||
            account.value is! List) {
          continue;
        }
        final entries = <_Entry>[];
        for (final item in account.value as List) {
          if (item is! Map || item['t'] is! String || item['at'] is! int) {
            continue;
          }
          final term = clean(item['t'] as String);
          final at = DateTime.fromMillisecondsSinceEpoch(item['at'] as int,
              isUtc: true);
          if (term == null || !at.isAfter(cutoff) || at.isAfter(latest)) {
            continue;
          }
          entries.add(_Entry(term, at));
        }
        entries.sort((a, b) => b.at.compareTo(a.at));
        final seen = <String>{};
        final unique = [
          for (final entry in entries)
            if (seen.add(_same(entry.term))) entry
        ];
        if (unique.isNotEmpty) {
          result[account.key as String] = unique.take(maxEntries).toList();
        }
      }
    } on FormatException {
      return <String, List<_Entry>>{};
    }
    return result;
  }

  String _encode(Map<String, List<_Entry>> accounts) => jsonEncode({
        'v': 1,
        'accounts': {
          for (final e in accounts.entries)
            e.key: [
              for (final entry in e.value)
                {
                  't': entry.term,
                  'at': entry.at.millisecondsSinceEpoch,
                }
            ]
        }
      });

  Future<Map<String, List<_Entry>>> _load() async {
    try {
      return _decode(await store.read());
    } catch (_) {
      return <String, List<_Entry>>{};
    }
  }

  Future<void> _save(Map<String, List<_Entry>> accounts) async {
    try {
      if (accounts.isEmpty) {
        await store.delete();
      } else {
        await store.write(_encode(accounts));
      }
    } catch (_) {
      // An unavailable secure store means no history, never a failed search.
    }
  }

  /// Newest first; expired entries are dropped from the store when seen.
  Future<List<String>> recent(String? accountId) => _serialized(() async {
        if (accountId == null || !isApiId(accountId)) return const <String>[];
        final accounts = await _load();
        await _save(accounts);
        return [for (final e in accounts[accountId] ?? const <_Entry>[]) e.term];
      });

  Future<void> add(String? accountId, String raw) => _serialized(() async {
        final term = clean(raw);
        if (accountId == null || !isApiId(accountId) || term == null) return;
        final accounts = await _load();
        final entries = [
          _Entry(term, _now().toUtc()),
          for (final e in accounts[accountId] ?? const <_Entry>[])
            if (_same(e.term) != _same(term)) e
        ];
        accounts[accountId] = entries.take(maxEntries).toList();
        await _save(accounts);
      });

  Future<void> remove(String? accountId, String term) =>
      _serialized(() async {
        if (accountId == null || !isApiId(accountId)) return;
        final accounts = await _load();
        accounts[accountId]
            ?.removeWhere((entry) => _same(entry.term) == _same(term));
        if (accounts[accountId]?.isEmpty ?? false) accounts.remove(accountId);
        await _save(accounts);
      });

  /// The visible Clear action: every entry of this account.
  Future<void> clear(String? accountId) => _serialized(() async {
        if (accountId == null || !isApiId(accountId)) return;
        final accounts = await _load();
        accounts.remove(accountId);
        await _save(accounts);
      });

  /// Sign-out: nothing of any account is left on the device.
  Future<void> clearAll() => _serialized(() async {
        try {
          await store.delete();
        } catch (_) {}
      });
}

class _Entry {
  const _Entry(this.term, this.at);
  final String term;
  final DateTime at;
}
