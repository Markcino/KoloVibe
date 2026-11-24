/// Fixed lists the Business service leaves open (it only checks a code pattern). Approved by the owner on
/// 24 November 2026 (Phase 6D decision A5); they are app policy, not service rules.
class Choice {
  const Choice(this.code, this.label);
  final String code;
  final String label;
}

const inquirySubjects = [
  Choice('order_question', 'An order'),
  Choice('opening_hours', 'Opening hours'),
  Choice('price_question', 'Prices'),
  Choice('availability', 'Availability'),
  Choice('general_question', 'Something else'),
];

const reportReasons = [
  Choice('misleading', 'Misleading or false'),
  Choice('spam', 'Spam'),
  Choice('abusive', 'Abusive or hateful'),
  Choice('personal_data', 'Shares personal information'),
  Choice('impersonation', 'Pretends to be someone else'),
  Choice('other', 'Something else'),
];

/// Only `manual_review` has been exercised by the service.
const verificationMethods = [Choice('manual_review', 'Document review')];

const evidenceKinds = [
  Choice('registration_number', 'Business registration number'),
  Choice('licence_number', 'Licence number'),
  Choice('tax_number', 'Tax number'),
  Choice('website_or_social_proof', 'Website or social page'),
  Choice('note', 'Note for the reviewer'),
];

const counties = [
  Choice('bomi', 'Bomi'),
  Choice('bong', 'Bong'),
  Choice('gbarpolu', 'Gbarpolu'),
  Choice('grand_bassa', 'Grand Bassa'),
  Choice('grand_cape_mount', 'Grand Cape Mount'),
  Choice('grand_gedeh', 'Grand Gedeh'),
  Choice('grand_kru', 'Grand Kru'),
  Choice('lofa', 'Lofa'),
  Choice('margibi', 'Margibi'),
  Choice('maryland', 'Maryland'),
  Choice('montserrado', 'Montserrado'),
  Choice('nimba', 'Nimba'),
  Choice('river_cess', 'River Cess'),
  Choice('river_gee', 'River Gee'),
  Choice('sinoe', 'Sinoe'),
];

const contactKinds = [
  Choice('phone', 'Phone'),
  Choice('email', 'Email'),
  Choice('website', 'Website'),
  Choice('social', 'Social page'),
];

const weekdays = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
];

String labelFor(List<Choice> choices, String code) {
  for (final choice in choices) {
    if (choice.code == code) return choice.label;
  }
  return code.replaceAll('_', ' ');
}
