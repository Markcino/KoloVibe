import 'package:flutter/material.dart';
import '../../core/network/api_client.dart';
import '../../app/screen_route.dart';
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
      if (mounted) acceptFollow(result, expected: !before);
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
        appBar: AppBar(title: const Text('Creator')),
        body: SafeArea(child: Builder(
          builder: (context) {
            if (loading) {
              return const Center(child: CircularProgressIndicator());
            }
            if (error != null) {
              final failure = error;
              final missing = failure is ApiFailure && failure.status == 404;
              return Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                Semantics(
                    liveRegion: true,
                    child: Text(missing
                        ? 'This creator is not available for public viewing.'
                        : 'Creators are temporarily unavailable.')),
                if (!missing)
                  OutlinedButton(
                    onPressed: load,
                    child: const Text('Try again'),
                  ),
              ]));
            }
            final creator = profile!;
            return ListView(padding: const EdgeInsets.all(24), children: [
              Text(
                  creator.displayName.isEmpty
                      ? '@${creator.handle}'
                      : creator.displayName,
                  style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 16),
              Text('@${creator.handle} · ${creator.location}'),
              Text(creator.bio),
              Text(followerCount == null
                  ? 'Followers unavailable'
                  : '$followerCount followers'),
              Text(creator.publishedVideoCount == null
                  ? 'Published count unavailable'
                  : '${creator.publishedVideoCount} published videos'),
              OutlinedButton(
                  onPressed: () => go(27),
                  child: const Text('Published videos')),
              if (followFailure != null &&
                  !(followFailure is ApiFailure &&
                      (followFailure as ApiFailure).status == 401))
                SystemFailureView(
                    error: followFailure!,
                    onRetry: load,
                    onSignIn: () => go(4)),
              FilledButton(
                  onPressed: updatingFollow
                      ? null
                      : following == null &&
                              widget.account != null &&
                              !(followFailure is ApiFailure &&
                                  (followFailure as ApiFailure).status == 401)
                          ? load
                          : toggleFollow,
                  child: Text(following == true ? 'Unfollow' : 'Follow')),
            ]);
          },
        )),
      );
}
