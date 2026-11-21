import '../../core/network/api_client.dart';
import '../account/live_account_repository.dart';
import 'live_own_creator_repository.dart';

class CreatorApplication {
  const CreatorApplication(this.accountId, this.status, this.creatorId);

  final String accountId;
  final String status;
  final String? creatorId;

  factory CreatorApplication.fromJson(Map<String, dynamic> data) {
    final accountId = data['account_id'];
    final status = data['status'];
    final creatorId = data['creator_id'];
    if (data.keys
            .toSet()
            .difference({'account_id', 'status', 'creator_id'}).isNotEmpty ||
        !isApiId(accountId) ||
        !{'invited', 'pending', 'approved', 'rejected'}.contains(status) ||
        creatorId != null && !isApiId(creatorId)) {
      throw const FormatException('Invalid creator application');
    }
    return CreatorApplication(
        accountId as String, status as String, creatorId as String?);
  }
}

class UploadEligibility {
  const UploadEligibility(this.eligible, this.creatorId);
  final bool eligible;
  final String? creatorId;

  factory UploadEligibility.fromJson(Map<String, dynamic> data) {
    final eligible = data['upload_eligible'];
    final creatorId = data['creator_id'];
    if (data.keys
            .toSet()
            .difference({'upload_eligible', 'creator_id'}).isNotEmpty ||
        eligible is! bool ||
        (eligible ? !isApiId(creatorId) : creatorId != null)) {
      throw const FormatException('Invalid upload eligibility');
    }
    return UploadEligibility(eligible, creatorId as String?);
  }
}

class LiveCreatorOnboardingRepository {
  const LiveCreatorOnboardingRepository(this.account);
  final LiveAccountRepository account;

  Future<CreatorApplication?> application() async {
    try {
      return CreatorApplication.fromJson(
          await account.authenticatedRequest('/creators/me/application'));
    } on ApiFailure catch (failure) {
      if (failure.status == 404) return null;
      rethrow;
    }
  }

  Future<UploadEligibility> eligibility() async {
    final result = UploadEligibility.fromJson(
        await account.authenticatedRequest('/creators/me/upload-eligibility'));
    if (result.eligible) {
      // Approval changes Identity's role and invalidates earlier sessions.
      // Read live /me before presenting Studio access; never infer a local role.
      final profile = await account.currentAccount();
      if (profile == null) {
        throw const ApiFailure(401, 'Sign in again to open Creator Studio.');
      }
      if (!profile.roles.contains('creator')) {
        throw const ApiFailure(503, 'Creator access is updating. Check again.');
      }
    }
    return result;
  }

  Future<CreatorApplication> submit(
      {required String handle,
      required bool adultAttested,
      required bool rightsAttested}) async {
    final trimmed = handle.trim();
    // DOC-205 `POST /creators/me/application`: ^[a-z0-9_]{3,30}$ and both attestations.
    if (creatorHandleProblem(trimmed) != null ||
        !adultAttested ||
        !rightsAttested) {
      throw const FormatException('Invalid creator handle');
    }
    return CreatorApplication.fromJson(await account.authenticatedRequest(
        '/creators/me/application',
        method: 'POST',
        body: {
          'handle': trimmed,
          'adult_attested': adultAttested,
          'rights_attested': rightsAttested,
        }));
  }
}
