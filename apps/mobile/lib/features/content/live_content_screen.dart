import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../shell/main_shell.dart';
import '../creators/live_creator_onboarding_repository.dart';
import 'live_content_repository.dart';

class LiveContentScreen extends StatefulWidget {
  const LiveContentScreen(
      {super.key,
      required this.route,
      required this.catalog,
      required this.repository,
      this.onboarding});

  final ScreenRoute route;
  final DesignCatalog catalog;
  final LiveContentRepository repository;
  final LiveCreatorOnboardingRepository? onboarding;

  @override
  State<LiveContentScreen> createState() => _LiveContentScreenState();
}

class _LiveContentScreenState extends State<LiveContentScreen> {
  final _items = <OwnedVideo>[];
  String? _cursor;
  String? _error;
  bool _loading = false;
  bool _loaded = false;
  bool _onboardingBusy = false;
  bool _onboardingLoaded = false;
  String? _onboardingError;
  CreatorApplication? _application;
  UploadEligibility? _eligibility;
  final _handle = TextEditingController();
  bool _adultAttested = false;
  bool _rightsAttested = false;

  @override
  void initState() {
    super.initState();
    if (widget.route.screen == 37 && widget.onboarding != null) {
      _loadOnboarding();
    } else {
      _load(reset: true);
    }
  }

  @override
  void dispose() {
    _handle.dispose();
    super.dispose();
  }

  Future<void> _loadOnboarding() async {
    if (_onboardingBusy) return;
    setState(() {
      _onboardingBusy = true;
      _onboardingError = null;
    });
    try {
      final eligibility = await widget.onboarding!.eligibility();
      final application = await widget.onboarding!.application();
      if (!mounted) return;
      setState(() {
        _eligibility = eligibility;
        _application = application;
        _onboardingLoaded = true;
      });
      if (eligibility.eligible) await _load(reset: true);
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => _onboardingError = failure.message);
    } on FormatException {
      if (mounted) {
        setState(() => _onboardingError = 'Creator status could not be read.');
      }
    } finally {
      if (mounted) setState(() => _onboardingBusy = false);
    }
  }

  Future<void> _submitApplication() async {
    final handle = _handle.text.trim();
    if (!RegExp(r'^[A-Za-z0-9_-]{1,40}$').hasMatch(handle) ||
        !_adultAttested ||
        !_rightsAttested) {
      _notify('Enter a valid handle and confirm both statements.');
      return;
    }
    setState(() {
      _onboardingBusy = true;
      _onboardingError = null;
    });
    try {
      final application = await widget.onboarding!.submit(
          handle: handle,
          adultAttested: _adultAttested,
          rightsAttested: _rightsAttested);
      if (!mounted) return;
      setState(() {
        _application = application;
        _onboardingBusy = false;
      });
      await _loadOnboarding();
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => _onboardingError = failure.message);
    } on FormatException {
      if (mounted) {
        setState(() => _onboardingError = 'Application could not be sent.');
      }
    } finally {
      if (mounted) setState(() => _onboardingBusy = false);
    }
  }

  Future<void> _load({bool reset = false}) async {
    if (_loading) return;
    setState(() {
      _loading = true;
      _error = null;
      if (reset) {
        _items.clear();
        _cursor = null;
      }
    });
    try {
      final page = await widget.repository.library(cursor: _cursor);
      if (!mounted) return;
      final known = _items.map((video) => video.id).toSet();
      if (page.items.any((video) => known.contains(video.id))) {
        throw const FormatException('Repeated video page');
      }
      setState(() {
        _items.addAll(page.items);
        _cursor = page.nextCursor;
        _loaded = true;
      });
    } on ApiFailure catch (failure) {
      if (mounted) setState(() => _error = failure.message);
    } on FormatException {
      if (mounted) {
        setState(() => _error = 'The video library response was invalid.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _edit(OwnedVideo video) async {
    var title = video.title;
    var description = video.description;
    final form = GlobalKey<FormState>();
    final changed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit draft'),
        content: Form(
          key: form,
          child: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextFormField(
                initialValue: title,
                maxLength: 160,
                decoration: const InputDecoration(labelText: 'Title'),
                onChanged: (value) => title = value,
                validator: (value) => value == null || value.trim().isEmpty
                    ? 'Enter a title'
                    : null,
              ),
              TextFormField(
                initialValue: description,
                maxLength: 2000,
                maxLines: 3,
                decoration: const InputDecoration(labelText: 'Description'),
                onChanged: (value) => description = value,
              ),
            ]),
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () {
                if (form.currentState?.validate() ?? false) {
                  Navigator.pop(context, true);
                }
              },
              child: const Text('Save')),
        ],
      ),
    );
    if (!mounted || changed != true) return;
    try {
      await widget.repository
          .editDraft(video, title: title, description: description);
      await _load(reset: true);
    } on ApiFailure catch (failure) {
      if (mounted) _notify(failure.message);
    } on FormatException {
      if (mounted) _notify('The draft could not be saved.');
    }
  }

  Future<void> _delete(OwnedVideo video) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete draft?'),
        content: const Text('This action cannot be undone.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Delete')),
        ],
      ),
    );
    if (!mounted || confirmed != true) return;
    try {
      await widget.repository.deleteDraft(video);
      await _load(reset: true);
    } on ApiFailure catch (failure) {
      if (mounted) _notify(failure.message);
    } on FormatException {
      if (mounted) _notify('The draft could not be deleted.');
    }
  }

  void _notify(String message) => ScaffoldMessenger.of(context)
      .showSnackBar(SnackBar(content: Text(message)));

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
            title: Text(widget.route.screen == 37
                ? 'Creator Studio'
                : 'My video library')),
        body: SafeArea(
            child: RefreshIndicator(
          onRefresh: widget.route.screen == 37 && widget.onboarding != null
              ? _loadOnboarding
              : () => _load(reset: true),
          child: ListView(padding: const EdgeInsets.all(16), children: [
            if (widget.route.screen == 37 && widget.onboarding != null) ...[
              if (_onboardingBusy && !_onboardingLoaded)
                const Center(child: CircularProgressIndicator()),
              if (_onboardingError != null) ...[
                Semantics(liveRegion: true, child: Text(_onboardingError!)),
                OutlinedButton(
                    onPressed: _onboardingBusy ? null : _loadOnboarding,
                    child: const Text('Retry creator status')),
              ],
              if (_onboardingLoaded && _eligibility?.eligible != true) ...[
                Text('Creator access',
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Text(switch (_application?.status) {
                  'invited' =>
                    'Your invitation is ready. Apply to create originals.',
                  'pending' => 'Your creator application is awaiting review.',
                  'approved' => 'Creator upload is currently restricted.',
                  'rejected' => 'Your creator application was not approved.',
                  _ => 'An invitation is required before you can apply.',
                }),
                if (_application?.status == 'invited') ...[
                  const SizedBox(height: 16),
                  TextField(
                      controller: _handle,
                      maxLength: 40,
                      decoration:
                          const InputDecoration(labelText: 'Creator handle')),
                  CheckboxListTile(
                    value: _adultAttested,
                    onChanged: _onboardingBusy
                        ? null
                        : (value) =>
                            setState(() => _adultAttested = value ?? false),
                    title: const Text('I confirm I am an adult.'),
                  ),
                  CheckboxListTile(
                    value: _rightsAttested,
                    onChanged: _onboardingBusy
                        ? null
                        : (value) =>
                            setState(() => _rightsAttested = value ?? false),
                    title: const Text('I have rights to my original content.'),
                  ),
                  FilledButton(
                      onPressed: _onboardingBusy ? null : _submitApplication,
                      child: const Text('Submit creator application')),
                ],
              ],
            ],
            if (widget.route.screen == 37 &&
                (widget.onboarding == null ||
                    _eligibility?.eligible == true)) ...[
              ListTile(
                title: const Text('Create an original'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  const route = ScreenRoute(41);
                  Navigator.of(context).pushNamed(route.name, arguments: route);
                },
              ),
              ListTile(
                title: const Text('My video library'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  const route = ScreenRoute(40);
                  Navigator.of(context).pushNamed(route.name, arguments: route);
                },
              ),
            ],
            if (widget.route.screen != 37 ||
                widget.onboarding == null ||
                _eligibility?.eligible == true) ...[
              if (_loading && !_loaded)
                const Center(child: CircularProgressIndicator()),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Semantics(liveRegion: true, child: Text(_error!)),
                ),
              if (_loaded && _items.isEmpty && !_loading && _error == null)
                const Center(child: Text('You have no videos yet.')),
              for (final video in _items)
                Card(
                    child: ListTile(
                  title: Text(video.title),
                  subtitle: Text(video.state),
                  trailing: video.canEditDraft
                      ? PopupMenuButton<String>(
                          tooltip: 'Manage draft',
                          onSelected: (action) {
                            if (action == 'edit') _edit(video);
                            if (action == 'delete') _delete(video);
                          },
                          itemBuilder: (_) => const [
                            PopupMenuItem(
                                value: 'edit', child: Text('Edit draft')),
                            PopupMenuItem(
                                value: 'delete', child: Text('Delete draft')),
                          ],
                        )
                      : null,
                )),
              if (_loading && _loaded)
                const Center(child: CircularProgressIndicator()),
              if (!_loading && (_cursor != null || _error != null))
                TextButton(
                    onPressed: () => _load(reset: _cursor == null),
                    child: Text(_error == null ? 'Load more' : 'Try again')),
            ],
          ]),
        )),
        bottomNavigationBar: widget.route.screen == 37
            ? MainShell(
                navigation: widget.catalog[37].named('Primary navigation')!,
                screen: 37,
                onSelected: (target) {
                  final route = ScreenRoute(target);
                  Navigator.of(context)
                      .pushReplacementNamed(route.name, arguments: route);
                },
              )
            : null,
      );
}
