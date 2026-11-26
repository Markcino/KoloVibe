import 'live_standing_repository.dart';

/// Wording for moderation notices and standing.
///
/// Every sentence restates a value from the server's closed vocabularies
/// (decision, appeal status, creator status). Reason codes are free-form and
/// have no approved per-code copy yet, so a code is shown as received and is
/// never turned into a policy claim.

String noticeDecisionLabel(String decision) => switch (decision) {
      'rejected' => 'Not approved',
      'removed' => 'Removed',
      'restricted' => 'Restricted',
      'restored' => 'Restored',
      _ => 'No decision',
    };

String noticeHeadline(String decision) => switch (decision) {
      'none' => 'No moderation decision.',
      'rejected' => 'This content wasn’t approved.',
      'restored' => 'This content was restored.',
      _ => 'Content availability has changed.',
    };

String noticeSummary(String decision) => switch (decision) {
      'rejected' =>
        'This content was not approved for publishing and is not available to viewers.',
      'removed' =>
        'This content has been removed and is unavailable to viewers.',
      'restricted' => 'This content is currently unavailable to viewers.',
      'restored' => 'A moderation decision restored this content.',
      _ => 'No moderation decision has been recorded for this content.',
    };

/// A default code the server records when a reviewer gave no policy code.
bool isDefaultReviewCode(String code) => code.startsWith('REVIEWED_');

String noticeReason(String? code) {
  if (code == null) return 'No reason code was recorded for this decision.';
  if (isDefaultReviewCode(code)) {
    return 'A moderation reviewer recorded this decision. No policy reason was specified.';
  }
  return 'Reason code: $code';
}

String appealStatusText(String status) => switch (status) {
      'open' => 'Your review request is under review.',
      'denied' => 'Your review request was denied.',
      'restored' =>
        'Your review request was accepted and the content was restored.',
      _ => 'Your review request status is unavailable.',
    };

/// The standing headline, body and publishing line for a creator status.
({String headline, String body, String publishing}) standingCopy(
    AccountStanding standing) {
  const restrictedBody =
      'Access to some or all KoloVibe features is currently restricted under the account policy.';
  const blocked =
      'You cannot upload or publish while this restriction applies.';
  switch (standing.creatorStatus) {
    case 'suspended':
      return (
        headline: 'Your creator account is suspended.',
        body: restrictedBody,
        publishing: blocked
      );
    case 'restricted':
      return (
        headline: 'Your creator account is restricted.',
        body: restrictedBody,
        publishing: blocked
      );
    case 'pending':
      return (
        headline: 'Your creator profile is pending review.',
        body: 'Creator features open once your profile is approved.',
        publishing: 'Publishing is unavailable until it is approved.'
      );
    case 'active':
      return (
        headline: 'Your creator account is active.',
        body: 'No restriction is recorded on your creator account.',
        publishing: standing.publishingAllowed
            ? 'You can publish your originals.'
            : 'Publishing is unavailable right now. Check that your email is verified.'
      );
    default:
      return (
        headline: 'You don’t have a creator profile.',
        body: 'Your account is active.',
        publishing: 'Publishing is unavailable until you become a creator.'
      );
  }
}
