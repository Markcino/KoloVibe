/// Route numbers for the Business screens. They continue after the 108 designed creator-content screens (M-001 to
/// M-108) and are **implementation-led, not visually approved**: no Figma frame exists for them (owner decision
/// A1, 24 November 2026). See docs/architecture/business/BIZ-Flutter_Screen_Inventory_PROPOSED.md.
class BusinessScreens {
  const BusinessScreens._();
  static const first = 109;
  static const last = 144;

  // D1 discovery
  static const home = 109;
  static const categories = 110;
  static const results = 111;
  static const filters = 112;
  static const detail = 113;
  static const hours = 114;
  static const contact = 115;
  static const reviews = 116;
  static const privacy = 117;
  // D2 customer
  static const ask = 118;
  static const myInquiries = 119;
  static const conversation = 120;
  static const writeReview = 121;
  static const myReviews = 122;
  static const editReview = 123;
  static const withdrawReview = 124;
  static const report = 125;
  // D3 owner
  static const myBusinesses = 126;
  static const register = 127;
  static const manage = 128;
  static const editProfile = 129;
  static const editContacts = 130;
  static const editHours = 131;
  static const profileStatus = 132;
  static const verification = 133;
  static const listing = 134;
  static const inbox = 135;
  static const inboxThread = 136;
  static const ownerReviews = 137;
  static const reviewInvitations = 138;
  static const team = 139;
  // D4 staff
  static const redeem = 140;
  static const switcher = 141;
  static const accessRemoved = 142;
  static const leave = 143;
  static const staffHome = 144;

  static bool contains(int screen) => screen >= first && screen <= last;
}
