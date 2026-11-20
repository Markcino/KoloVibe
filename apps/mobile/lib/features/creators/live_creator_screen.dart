import 'package:flutter/material.dart';
import '../../core/network/api_client.dart';
import '../../app/screen_route.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../../shared/widgets/live_state_view.dart';
import '../system/system_ui.dart';
import '../account/live_account_repository.dart';
import 'live_creator_repository.dart';

class LiveCreatorScreen extends StatefulWidget {
  const LiveCreatorScreen(
      {super.key, required this.id, required this.repository, this.account});
  final String id;
  final LiveCreatorRepository repository;
  final LiveAccountRepository? account;

  @override
  State<LiveCreatorScreen> createState() => _LiveCreatorScreenState();
}

class _LiveCreatorScreenState extends State<LiveCreatorScreen> {
  LiveCreator? profile;
  Object? error;
  bool loading = true;
  bool? following;
  bool updatingFollow = false;
  int? followerCount;
  Object? followFailure;
  void go(int screen) {
    final route =
        ScreenRoute(screen, entityId: screen == 27 ? widget.id : null);
    Navigator.of(context).pushNamed(route.name, arguments: route);
  }

  void acceptFollow(Map<String, dynamic> value, {bool? expected}) {
    if (value.length != 3 ||
        value['creator_id'] != widget.id ||
        value['following'] is! bool ||
        value['follower_count'] is! int ||
        (value['follower_count'] as int) < 0 ||
        expected != null && value['following'] != expected) {
      throw const FormatException('Invalid follow response');
    }
    following = value['following'] as bool;
    followerCount = value['follower_count'] as int;
  }

  Future<void> toggleFollow() async {
    if (following == null || widget.account == null) {
      go(4);
      return;
    }
    if (updatingFollow) return;
    final before = following!, count = followerCount;
    setState(() {
      following = !before;
      updatingFollow = true;
      if (count != null) followerCount = count + (before ? -1 : 1);
    });
    try {
      final result = await widget.account!.authenticatedRequest(
          '/creators/${widget.id}/follow',
          method: before ? 'DELETE' : 'PUT');
      if (mounted) {
        acceptFollow(result, expected: !before);
        if (!before) {
          final shown = profile == null || profile!.displayName.isEmpty
              ? '@${profile?.handle ?? ''}'
              : profile!.displayName;
          ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('You’re now following $shown')));
        }
      }
    } catch (failure) {
      if (mounted) {
        following = before;
        followerCount = count;
        if (failure is ApiFailure && failure.status == 401) {
          go(4);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
              content: Text(
                  'The follow change could not be confirmed. Try again.')));
        }
      }
    } finally {
      if (mounted) setState(() => updatingFollow = false);
    }
  }

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
      followFailure = null;
    });
    try {
      final value = await widget.repository.detail(widget.id);
      if (mounted) {
        setState(() {
          profile = value;
          followerCount = value.followerCount;
        });
      }
      if (widget.account != null) {
        try {
          final result = await widget.account!
              .authenticatedRequest('/creators/${widget.id}/follow');
          if (mounted) setState(() => acceptFollow(result));
        } catch (failure) {
          if (mounted) setState(() => followFailure = failure);
        }
      }
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => error = failure);
    } on FormatException catch (failure) {
      if (mounted) setState(() => error = failure);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
            title: Text(profile == null || profile!.displayName.isEmpty
                ? 'Creator'
                : profile!.displayName)),
        body: SafeArea(child: Builder(
          builder: (context) {
            if (loading) {
              return const Center(child: CircularProgressIndicator());
            }
            if (error != null) {
              final failure = error;
              final missing = failure is ApiFailure && failure.status == 404;
              return missing
                  ? const LiveStateView.empty(
                      title: 'Creator not available',
                      message:
                          'This creator is not available for public viewing.',
                      icon: Icons.person_off_outlined)
                  : LiveStateView.empty(
                      title: 'Creator unavailable',
                      message: 'Creators are temporarily unavailable.',
                      icon: Icons.cloud_off_outlined,
                      actionLabel: 'Try again',
                      onAction: load);
            }
            final creator = profile!;
            final name = creator.displayName.isEmpty
                ? '@${creator.handle}'
                : creator.displayName;
            final signInRejected = followFailure is ApiFailure &&
                (followFailure as ApiFailure).status == 401;
            return ListView(
                padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
                children: [
                  Row(children: [
                    KoloAvatar(name: name, size: 64),
                    const SizedBox(width: 12),
                    Expanded(
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                          Text(name,
                              style: KoloVibeText.body(16,
                                  weight: FontWeight.w600,
                                  color: KoloVibeColors.navy)),
                          Text(
                              '@${creator.handle}${creator.location.isEmpty ? '' : ' · ${creator.location}'}',
                              style: KoloVibeText.body(12)),
                        ])),
                  ]),
                  if (creator.bio.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Text(creator.bio,
                        style: KoloVibeText.body(14, height: 1.5)),
                  ],
                  const SizedBox(height: 16),
                  Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Expanded(
                        child: _Metric(
                            label: 'Followers',
                            value: followerCount,
                            unavailable: 'Unavailable')),
                    const SizedBox(width: 12),
                    Expanded(
                        child: _Metric(
                            label: 'Published videos',
                            value: creator.publishedVideoCount,
                            unavailable: 'Unavailable')),
                  ]),
                  const SizedBox(height: 16),
                  if (followFailure != null && !signInRejected)
                    SystemFailureView(
                        error: followFailure!,
                        onRetry: load,
                        onSignIn: () => go(4)),
                  if (following == true)
                    FilledButton.icon(
                        onPressed: updatingFollow ? null : toggleFollow,
                        style: FilledButton.styleFrom(
                            backgroundColor: KoloVibeColors.softBlue,
                            foregroundColor: KoloVibeColors.navy),
                        icon: const Icon(Icons.check, size: 18),
                        label: const Text('Following'))
                  else
                    FilledButton(
                        onPressed: updatingFollow
                            ? null
                            : following == null &&
                                    widget.account != null &&
                                    !signInRejected
                                ? load
                                : toggleFollow,
                        child: Text('Follow ${_firstName(name)}')),
                  if (following == true) ...[
                    const SizedBox(height: 16),
                    KoloNote(
                        title: 'You’re connected',
                        message:
                            '${_firstName(name)}’s new videos can appear in your Following feed. Tap Following again to unfollow.',
                        asset: KoloIcons.circleCheck,
                        tone: KoloNoteTone.success),
                  ],
                  const SizedBox(height: 12),
                  OutlinedButton(
                      onPressed: () => go(27),
                      child: const Text('See all videos')),
                ]);
          },
        )),
      );
}

String _firstName(String name) {
  final first = name.trim().split(RegExp(r'\s+')).first;
  return first.isEmpty ? 'creator' : first;
}

/// Large numeral with a small caption, as drawn on the creator profile.
/// Counts of 1,000 or more are abbreviated (2.8K) like the design.
class _Metric extends StatelessWidget {
  const _Metric(
      {required this.label, required this.value, required this.unavailable});
  final String label, unavailable;
  final int? value;

  static String compact(int value) {
    if (value < 1000) return '$value';
    if (value < 1000000) {
      final k = value / 1000;
      return '${k.toStringAsFixed(k >= 10 ? 0 : 1).replaceFirst(RegExp(r'\.0$'), '')}K';
    }
    final m = value / 1000000;
    return '${m.toStringAsFixed(m >= 10 ? 0 : 1).replaceFirst(RegExp(r'\.0$'), '')}M';
  }

  @override
  Widget build(BuildContext context) => Semantics(
        container: true,
        label: value == null ? '$label $unavailable' : '$label $value',
        excludeSemantics: true,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: KoloVibeText.body(11)),
          const SizedBox(height: 5),
          Text(value == null ? '—' : compact(value!),
              style: KoloVibeText.heading(26)),
        ]),
      );
}
