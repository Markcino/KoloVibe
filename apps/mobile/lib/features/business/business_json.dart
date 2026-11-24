import '../../core/network/api_client.dart' show isApiId;

/// Strict parsing for Business answers. The app trusts nothing it has not shape-checked: a missing or extra key, a
/// wrong type or an out-of-range value is a [FormatException], which the screens show as an ordinary failure.
Never _bad(String what) => throw FormatException('Invalid $what');

Map<String, dynamic> exact(Object? value, String what, Set<String> keys,
    {Set<String> optional = const {}}) {
  if (value is! Map<String, dynamic>) _bad(what);
  final present = value.keys.toSet();
  if (!present.containsAll(keys) ||
      present.difference(keys.union(optional)).isNotEmpty) {
    _bad(what);
  }
  return value;
}

String text(Object? value, String what, {int min = 0, int max = 2000}) {
  if (value is! String || value.length < min || value.length > max) _bad(what);
  return value;
}

String? textOrNull(Object? value, String what, {int min = 0, int max = 2000}) =>
    value == null ? null : text(value, what, min: min, max: max);

bool flag(Object? value, String what) {
  if (value is! bool) _bad(what);
  return value;
}

int whole(Object? value, String what, {int min = 0, int max = 1 << 30}) {
  if (value is! int || value < min || value > max) _bad(what);
  return value;
}

String ident(Object? value, String what) {
  if (!isApiId(value)) _bad(what);
  return value as String;
}

String? identOrNull(Object? value, String what) =>
    value == null ? null : ident(value, what);

/// An ISO 8601 time that carries an offset; a time without one is ambiguous and refused.
DateTime moment(Object? value, String what) {
  if (value is! String || !RegExp(r'(Z|[+-]\d{2}:\d{2})$').hasMatch(value)) {
    _bad(what);
  }
  final parsed = DateTime.tryParse(value);
  if (parsed == null) _bad(what);
  return parsed;
}

DateTime? momentOrNull(Object? value, String what) =>
    value == null ? null : moment(value, what);

T choice<T>(Object? value, String what, Map<String, T> allowed) {
  final found = value is String ? allowed[value] : null;
  if (found == null) _bad(what);
  return found;
}

List<T> listOf<T>(Object? value, String what, T Function(Object?) parse,
    {int max = 200}) {
  if (value is! List || value.length > max) _bad(what);
  return List.unmodifiable(value.map(parse));
}

String? cursor(Object? value, String what) {
  if (value == null) return null;
  return text(value, what, min: 1, max: 600);
}
