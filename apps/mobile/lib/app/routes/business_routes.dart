import 'package:flutter/widgets.dart';

import '../../features/business/business_customer_screens.dart';
import '../../features/business/business_discovery_screens.dart';
import '../../features/business/business_inbox_screens.dart';
import '../../features/business/business_owner_screens.dart';
import '../../features/business/business_staff_screens.dart';
import '../../features/business/business_pending_screen.dart';
import '../../features/business/business_screens.dart';
import '../../features/business/business_ui.dart';
import 'route_context.dart';

/// Business discovery, customer, owner and staff screens (M-109–M-144). These are native screens built from the design
/// system (owner decision A1); they are not part of the 108-screen design catalog.
Widget? businessRoute(RouteContext context) {
  final route = context.route;
  if (!route.isBusiness) return null;
  // Business numbers have no design recipe, so the generic design screen must never see them.
  final repository = context.dependencies.liveBusiness;
  final catalog = context.catalog;
  if (repository == null) {
    return BusinessPendingScreen(
        route: route, catalog: catalog, available: false);
  }
  // Screens that are about one business, thread or review need its identifier from the route.
  final id = route.entityId;
  return switch (route.screen) {
    BusinessScreens.home =>
      BusinessHomeScreen(repository: repository, catalog: catalog),
    BusinessScreens.categories =>
      BusinessCategoriesScreen(repository: repository, catalog: catalog),
    BusinessScreens.results => BusinessResultsScreen(
        repository: repository, catalog: catalog, encodedFilters: id),
    BusinessScreens.filters => BusinessFiltersScreen(
        repository: repository, catalog: catalog, encodedFilters: id),
    BusinessScreens.detail when id != null => BusinessDetailScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.hours when id != null => BusinessHoursScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.contact when id != null => BusinessContactScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.reviews when id != null => BusinessReviewsScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.privacy => BusinessPrivacyScreen(catalog: catalog),
    BusinessScreens.ask when id != null => BusinessAskScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.myInquiries =>
      BusinessMyInquiriesScreen(repository: repository, catalog: catalog),
    BusinessScreens.conversation when id != null => BusinessConversationScreen(
        repository: repository, catalog: catalog, threadId: id),
    BusinessScreens.writeReview when ReviewTarget.decode(id) != null =>
      BusinessWriteReviewScreen(
          repository: repository,
          catalog: catalog,
          target: ReviewTarget.decode(id)!),
    BusinessScreens.myReviews =>
      BusinessMyReviewsScreen(repository: repository, catalog: catalog),
    BusinessScreens.editReview when id != null => BusinessEditReviewScreen(
        repository: repository, catalog: catalog, reviewId: id),
    BusinessScreens.withdrawReview when id != null =>
      BusinessWithdrawReviewScreen(
          repository: repository, catalog: catalog, reviewId: id),
    BusinessScreens.report when ReportTarget.decode(id) != null =>
      BusinessReportScreen(
          repository: repository,
          catalog: catalog,
          target: ReportTarget.decode(id)!),
    BusinessScreens.myBusinesses => BusinessMyBusinessesScreen(
        repository: repository,
        catalog: catalog,
        context: context.dependencies.businessContext),
    BusinessScreens.register =>
      BusinessRegisterScreen(repository: repository, catalog: catalog),
    BusinessScreens.manage when id != null => BusinessManageScreen(
        repository: repository,
        catalog: catalog,
        businessId: id,
        businessContext: context.dependencies.businessContext),
    BusinessScreens.staffHome when id != null => BusinessManageScreen(
        repository: repository,
        catalog: catalog,
        businessId: id,
        businessContext: context.dependencies.businessContext,
        screen: BusinessScreens.staffHome,
        title: 'Your business'),
    BusinessScreens.redeem => BusinessRedeemScreen(
        repository: repository,
        catalog: catalog,
        context: context.dependencies.businessContext),
    BusinessScreens.switcher => BusinessSwitcherScreen(
        repository: repository,
        catalog: catalog,
        context: context.dependencies.businessContext),
    BusinessScreens.accessRemoved => BusinessAccessRemovedScreen(
        catalog: catalog, context: context.dependencies.businessContext),
    BusinessScreens.leave when id != null => BusinessLeaveScreen(
        repository: repository,
        catalog: catalog,
        businessId: id,
        context: context.dependencies.businessContext),
    BusinessScreens.editProfile when id != null => BusinessEditProfileScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.editContacts when id != null => BusinessEditContactsScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.editHours when id != null => BusinessEditHoursScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.profileStatus when id != null =>
      BusinessProfileStatusScreen(
          repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.verification when id != null => BusinessVerificationScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.listing when id != null => BusinessListingScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.inbox when id != null => BusinessInboxScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.inboxThread
        when ReviewTarget.decode(id)?.threadId != null =>
      BusinessInboxThreadScreen(
          repository: repository,
          catalog: catalog,
          target: ReviewTarget.decode(id)!),
    BusinessScreens.ownerReviews when id != null => BusinessOwnerReviewsScreen(
        repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.reviewInvitations when id != null =>
      BusinessReviewInvitationsScreen(
          repository: repository, catalog: catalog, businessId: id),
    BusinessScreens.team when id != null => BusinessTeamScreen(
        repository: repository, catalog: catalog, businessId: id),
    _ => BusinessPendingScreen(route: route, catalog: catalog),
  };
}
