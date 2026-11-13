import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';

/// DOC-205 `CreatorUpdate.handle`: new handles and handle edits.
final creatorHandlePattern = RegExp(r'^[a-z0-9_]{3,30}$');

/// Existing handles may predate the stricter rule (DOC-205 `OwnCreator.handle`).
final _storedHandlePattern = RegExp(r'^[a-zA-Z0-9_-]{1,40}$');

const _fieldLimits = {'display_name': 80, 'bio': 500, 'location': 80};

/// A user-facing reason the handle is not acceptable, or null when it is.
String? creatorHandleProblem(String handle) {
  if (handle.isEmpty) return 'Enter a handle.';
  if (handle.length < 3 || handle.length > 30) {
    return 'Handles are 3 to 30 characters.';
  }
  if (handle != handle.toLowerCase()) return 'Use lowercase letters only.';
  if (!creatorHandlePattern.hasMatch(handle)) {
    return 'Spaces aren’t allowed. Use only letters, numbers and underscores.';
  }
  return null;
}

/// The signed-in creator's own profile (`GET /creators/me`).
class OwnCreator {
  const OwnCreator(this.id, this.userId, this.handle, this.displayName,
      this.bio, this.location);

  final String id, userId, handle, displayName, bio, location;

  /// Name to show: the display name, else the handle.
  String get title => displayName.isEmpty ? '@$handle' : displayName;

  factory OwnCreator.fromJson(Map<String, dynamic> data) {
    const keys = {
      'id',
      'user_id',
      'handle',
      'display_name',
      'bio',
      'location',
      'status'
    };
    final handle = data['handle'];
    final name = data['display_name'];
    final bio = data['bio'];
    final location = data['location'];
    if (data.keys.toSet().difference(keys).isNotEmpty ||
        !data.keys.toSet().containsAll(keys) ||
        !isApiId(data['id']) ||
        !isApiId(data['user_id']) ||
        data['status'] != 'active' ||
        handle is! String ||
        !_storedHandlePattern.hasMatch(handle) ||
        name is! String ||
        name.length > 80 ||
        bio is! String ||
        bio.length > 500 ||
        location is! String ||
        location.length > 80) {
      throw const FormatException('Invalid creator profile');
    }
    return OwnCreator(data['id'] as String, data['user_id'] as String, handle,
        name, bio, location);
  }
}

/// Own creator profile reads and edits. All requests are authenticated; the
/// gateway derives the creator from the session, never from the client.
class LiveOwnCreatorRepository {
  const LiveOwnCreatorRepository(this.account);
  final LiveAccountRepository account;

  Future<OwnCreator> profile() async =>
      OwnCreator.fromJson(await account.authenticatedRequest('/creators/me'));

  /// Sends only the fields that differ from [current]. Text is trimmed.
  /// Throws [FormatException] for input the server would reject, or when
  /// nothing changed, before any request is made.
  Future<OwnCreator> update(OwnCreator current,
      {String? displayName,
      String? bio,
      String? location,
      String? handle}) async {
    final candidates = <String, String>{
      if (displayName != null) 'display_name': displayName.trim(),
      if (bio != null) 'bio': bio.trim(),
      if (location != null) 'location': location.trim(),
      if (handle != null) 'handle': handle.trim(),
    };
    final existing = {
      'display_name': current.displayName,
      'bio': current.bio,
      'location': current.location,
      'handle': current.handle,
    };
    final body = <String, Object?>{
      for (final entry in candidates.entries)
        if (entry.value != existing[entry.key]) entry.key: entry.value,
    };
    if (body.isEmpty) throw const FormatException('Nothing to save');
    for (final entry in body.entries) {
      final value = entry.value as String;
      final limit = _fieldLimits[entry.key];
      if (limit != null && value.length > limit ||
          entry.key == 'handle' && creatorHandleProblem(value) != null ||
          value.runes.any((c) =>
              c < 32 && !(entry.key == 'bio' && '\n\r\t'.runes.contains(c)))) {
        throw const FormatException('Invalid creator profile');
      }
    }
    final result = OwnCreator.fromJson(await account
        .authenticatedRequest('/creators/me', method: 'PATCH', body: body));
    final returned = {
      'display_name': result.displayName,
      'bio': result.bio,
      'location': result.location,
      'handle': result.handle,
    };
    if (result.id != current.id ||
        result.userId != current.userId ||
        body.entries.any((e) => returned[e.key] != e.value)) {
      throw const FormatException('Mismatched creator profile');
    }
    return result;
  }
}
