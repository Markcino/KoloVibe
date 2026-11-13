import 'package:kolovibe/core/network/api_client.dart';
import 'package:kolovibe/features/creators/live_creator_onboarding_repository.dart';
import 'package:kolovibe/features/creators/live_creator_repository.dart';
import 'package:kolovibe/features/creators/live_own_creator_repository.dart';

import 'upload_fakes.dart';

const offline = ApiFailure(503, 'The service is unavailable. Please try again.',
    offline: true);
const expired = ApiFailure(401, 'Session expired');

OwnCreator ownCreator(
        {String handle = 'amakollie',
        String name = 'Ama Kollie',
        String bio = 'Finding the cinema in the everyday.',
        String location = 'Monrovia'}) =>
    OwnCreator(creatorId, accountId, handle, name, bio, location);

/// Scripted onboarding state. Mocked: no HTTP.
class ScriptedOnboarding extends LiveCreatorOnboardingRepository {
  ScriptedOnboarding() : super(unusedAccount());

  bool eligible = false;
  String? status; // null means "no application" (404)
  final List<Object> failures = [];
  final submissions = <Map<String, Object?>>[];
  Object? submitFailure;
  int loads = 0;

  @override
  Future<UploadEligibility> eligibility() async {
    loads++;
    if (failures.isNotEmpty) throw failures.removeAt(0);
    return UploadEligibility(eligible, eligible ? creatorId : null);
  }

  @override
  Future<CreatorApplication?> application() async => status == null
      ? null
      : CreatorApplication(accountId, status!, eligible ? creatorId : null);

  @override
  Future<CreatorApplication> submit(
      {required String handle,
      required bool adultAttested,
      required bool rightsAttested}) async {
    submissions.add({
      'handle': handle,
      'adult': adultAttested,
      'rights': rightsAttested,
    });
    final failure = submitFailure;
    if (failure != null) {
      submitFailure = null;
      throw failure;
    }
    status = 'pending';
    return const CreatorApplication(accountId, 'pending', null);
  }
}

/// Scripted own-profile service. Mocked: no HTTP.
class ScriptedOwnCreator extends LiveOwnCreatorRepository {
  ScriptedOwnCreator() : super(unusedAccount());

  OwnCreator current = ownCreator();
  Object? profileFailure, updateFailure;
  int reads = 0;
  final updates = <Map<String, String?>>[];

  @override
  Future<OwnCreator> profile() async {
    reads++;
    final failure = profileFailure;
    if (failure != null) throw failure;
    return current;
  }

  @override
  Future<OwnCreator> update(OwnCreator current,
      {String? displayName,
      String? bio,
      String? location,
      String? handle}) async {
    updates.add({
      'display_name': displayName,
      'bio': bio,
      'location': location,
      'handle': handle,
    });
    final failure = updateFailure;
    if (failure != null) {
      updateFailure = null;
      throw failure;
    }
    this.current = OwnCreator(
        current.id,
        current.userId,
        handle?.trim() ?? current.handle,
        displayName?.trim() ?? current.displayName,
        bio?.trim() ?? current.bio,
        location?.trim() ?? current.location);
    return this.current;
  }
}

/// Public creator read used only for the published-video count.
class CountingPublicCreators extends LiveCreatorRepository {
  CountingPublicCreators(this.count)
      : super(ApiClient('https://api.example.test/api/v1'));

  final int? count;
  Object? failure;

  @override
  Future<LiveCreator> detail(String id) async {
    if (failure != null) throw failure!;
    return LiveCreator(id, accountId, 'amakollie', '',
        publishedVideoCount: count);
  }
}
