import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../shared/widgets/live_state_view.dart';
import '../creators/live_creator_onboarding_repository.dart';
import 'live_content_repository.dart';
import 'live_upload_controller.dart';

/// Opens the platform video picker; replaced in tests.
typedef VideoPicker = Future<XFile?> Function();

Future<XFile?> _pickFromGallery() =>
    ImagePicker().pickVideo(source: ImageSource.gallery);

/// Live upload journey: M-041 entry, M-042 select, M-043 check, M-044 story,
/// M-046 uploading, M-047 interrupted, M-048 failed, M-049 preparing.
/// M-045 (cover) is not offered; the server chooses the cover frame.
class LiveCreateOriginalScreen extends StatefulWidget {
  const LiveCreateOriginalScreen(
      {super.key,
      required this.content,
      required this.onboarding,
      this.pickVideo = _pickFromGallery,
      this.controller});

  final LiveContentRepository content;
  final LiveCreatorOnboardingRepository onboarding;
  final VideoPicker pickVideo;

  /// Test seam for a pre-built controller.
  final LiveUploadController? controller;

  @override
  State<LiveCreateOriginalScreen> createState() =>
      _LiveCreateOriginalScreenState();
}

class _LiveCreateOriginalScreenState extends State<LiveCreateOriginalScreen> {
  late final LiveUploadController controller;
  final title = TextEditingController();
  final description = TextEditingController();
  final hashtags = TextEditingController();
  String? category;

  @override
  void initState() {
    super.initState();
    controller = widget.controller ??
        LiveUploadController(widget.content, widget.onboarding);
    controller.addListener(_refresh);
    controller.checkEligibility();
  }

  void _refresh() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    controller.removeListener(_refresh);
    controller.dispose();
    title.dispose();
    description.dispose();
    hashtags.dispose();
    super.dispose();
  }

  Future<void> _select() async {
    try {
      final file = await widget.pickVideo();
      if (file != null) await controller.select(file);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('The video picker could not open. Try again.')));
      }
    }
  }

  void _go(int screen) {
    final route = ScreenRoute(screen, returnTo: screen == 4 ? 41 : null);
    Navigator.of(context).pushNamed(route.name, arguments: route);
  }

  static const _failureCopy = {
    'invalid_media':
        "The service couldn't validate this video's format. Choose an exported MP4 that meets the current requirements.",
    'upload_missing':
        'The service did not confirm receipt of this video. It has not been published.',
    'upload_changed':
        'The file changed while it was uploading. Upload it again.',
    'processing_unavailable':
        'Video preparation is temporarily unavailable. Try again shortly.',
    'poster_failed': "A cover image couldn't be prepared. Try again.",
    'cover_out_of_range': 'The cover time falls outside the video. Try again.',
  };

  Widget _message(String text) =>
      Semantics(liveRegion: true, child: Text(text));

  List<Widget> _panel(BuildContext context) {
    final c = controller;
    switch (c.phase) {
      case UploadPhase.checkingAccess:
        return const [Text('Checking creator access…')];
      case UploadPhase.accessFailed:
        return [
          _message(c.error ?? 'Creator access could not be checked.'),
          OutlinedButton(
              onPressed: c.checkEligibility,
              child: const Text('Retry creator access')),
        ];
      case UploadPhase.ineligible:
        return [
          const Text('Creator upload is not available for this account.'),
          const Text('Uploads open once your creator application is approved.'),
          OutlinedButton(
              onPressed: c.checkEligibility, child: const Text('Check again')),
        ];
      case UploadPhase.signedOut:
        return [
          LiveStateView.failure(const ApiFailure(401, 'expired'),
              onSignIn: () => _go(4)),
        ];
      case UploadPhase.restricted:
        return [
          LiveStateView.failure(ApiFailure(
              403,
              c.error ??
                  'Uploading is not available for this account right now.')),
          const Text(
              'Your account or creator profile may be restricted. Nothing was published.'),
          OutlinedButton(
              onPressed: c.checkEligibility, child: const Text('Check again')),
        ];
      case UploadPhase.editing:
        return _editing(context);
      case UploadPhase.uploading:
        return _uploading();
      case UploadPhase.interrupted:
        return _interrupted();
      case UploadPhase.failed:
        return _failed();
      case UploadPhase.preparing:
        return _preparing();
      case UploadPhase.settled:
        return _settled();
    }
  }

  List<Widget> _steps(String current) => [
        Text(current, style: Theme.of(context).textTheme.labelLarge),
        const SizedBox(height: 8),
      ];

  List<Widget> _editing(BuildContext context) {
    final c = controller;
    final errors = c.detailsErrors.fields;
    final locked = c.draft != null;
    return [
      ..._steps(c.selected == null ? '1 · File' : '2 · Details'),
      Text('Choose your video', style: Theme.of(context).textTheme.titleMedium),
      const Text(
          'Bring an original film, performance or moment to the KoloVibe community.'),
      const Text('Select an MP4 original under 50 MB.'),
      const SizedBox(height: 12),
      OutlinedButton.icon(
        onPressed: c.canPickFile ? _select : null,
        icon: const Icon(Icons.video_library_outlined),
        label: Text(c.selected == null ? 'Select a video' : 'Choose another'),
      ),
      if (c.selected case final file?) ...[
        Text('${file.name} · ${c.selectedBytes} bytes'),
        const Text('File checked · Ready for details'),
      ] else
        const Text(
            'Before you upload: choose content you own or have permission to share.'),
      if (c.selected != null) ...[
        const SizedBox(height: 16),
        TextField(
          controller: title,
          enabled: !locked,
          maxLength: 160,
          decoration: InputDecoration(
              labelText: 'Title · Required', errorText: errors['title']),
        ),
        TextField(
          controller: description,
          enabled: !locked,
          maxLength: 2000,
          maxLines: 4,
          decoration: InputDecoration(
              labelText: 'Description', errorText: errors['description']),
        ),
        DropdownButtonFormField<String>(
          isExpanded: true,
          initialValue: category,
          decoration: InputDecoration(
              labelText: 'Category · Required', errorText: errors['category']),
          items: [
            for (final entry in videoCategories.entries)
              DropdownMenuItem(value: entry.key, child: Text(entry.value)),
          ],
          onChanged:
              locked ? null : (value) => setState(() => category = value),
        ),
        TextField(
          controller: hashtags,
          enabled: !locked,
          decoration: InputDecoration(
              labelText: 'Hashtags · Optional',
              helperText: 'Up to five, for example #monrovia #art',
              errorText: errors['tags']),
        ),
        const SizedBox(height: 12),
        FilledButton(
          onPressed: () =>
              c.submit(title.text, description.text, category, hashtags.text),
          child: Text(locked ? 'Upload again' : 'Create and upload'),
        ),
      ],
    ];
  }

  List<Widget> _uploading() {
    final c = controller;
    final progress = c.progress;
    return [
      ..._steps('3 · Upload'),
      Text('Uploading your original',
          style: Theme.of(context).textTheme.titleMedium),
      Semantics(
        label: 'Upload progress',
        value: progress == null ? null : '${(progress * 100).round()} percent',
        child: LinearProgressIndicator(value: progress),
      ),
      if (progress != null) Text('${(progress * 100).round()}%'),
      const Text(
          'Transferring video securely… Keep KoloVibe open until this step completes.'),
    ];
  }

  List<Widget> _interrupted() => [
        Text('Upload interrupted',
            style: Theme.of(context).textTheme.titleMedium),
        const Text('Upload not completed'),
        _message(controller.error ??
            'The transfer was interrupted. Reconnect before trying again.'),
        const Text(
            'Your original on this device has not changed. It has not been published.'),
        FilledButton(
            onPressed: controller.retry,
            child: const Text('Check connection and retry')),
        if (controller.canPickFile)
          OutlinedButton(
              onPressed: _select,
              child: const Text('Select a different video')),
      ];

  List<Widget> _failed() {
    final reason = controller.status?.failureReason;
    final c = controller;
    final retryable = c.status?.retryable ?? c.selected != null;
    return [
      Text('Upload failed', style: Theme.of(context).textTheme.titleMedium),
      const Text("Your upload couldn't be completed"),
      _message(_failureCopy[reason] ??
          c.error ??
          'The service did not confirm receipt of this video. It has not been published.'),
      if (reason == 'invalid_media')
        FilledButton(
            onPressed: _select, child: const Text('Select a different video'))
      else if (retryable && c.selected != null)
        FilledButton(onPressed: c.retry, child: const Text('Retry upload'))
      else
        FilledButton(
            onPressed: _select, child: const Text('Select the video again')),
      OutlinedButton(
          onPressed: () => _go(40), child: const Text('Return to my library')),
    ];
  }

  List<Widget> _preparing() {
    final c = controller;
    final status = c.status;
    final transient = status != null &&
        status.state == 'processing' &&
        status.failureReason != null;
    return [
      Text('Preparing your video',
          style: Theme.of(context).textTheme.titleMedium),
      const Text('Upload received'),
      const Text('Your story is taking shape.'),
      const LinearProgressIndicator(),
      const Text('Processing time varies. Your video is not public yet.'),
      if (transient) ...[
        _message(_failureCopy[status.failureReason] ??
            'Preparation did not finish.'),
        if (status.retryable)
          FilledButton(
              onPressed: c.retryPreparation,
              child: const Text('Retry preparation')),
      ],
      if (c.stalePreparation) ...[
        const Text("Still preparing. We've stopped checking automatically."),
        OutlinedButton(
            onPressed: c.refreshStatus, child: const Text('Check again')),
      ],
      if (c.error case final message? when !transient) _message(message),
      OutlinedButton(
          onPressed: () => _go(40), child: const Text('Return to my library')),
      const Text(
          'Next: content review. Once preparation completes, your video follows the applicable review process.'),
    ];
  }

  List<Widget> _settled() {
    final state = controller.status?.state;
    final text = switch (state) {
      'review' => 'Your video is waiting for review. It is not public yet.',
      'published' => 'Your video is published.',
      'rejected' => "Your video wasn't approved for publication.",
      'removed' => 'Your video has been removed.',
      _ => 'Your video status has changed.',
    };
    return [
      Text('Upload received', style: Theme.of(context).textTheme.titleMedium),
      Semantics(liveRegion: true, child: Text('Video status: $state')),
      Text(text),
      OutlinedButton(
          onPressed: () => _go(40), child: const Text('Return to my library')),
    ];
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Create an original')),
        body: SafeArea(
          child: ListView(padding: const EdgeInsets.all(20), children: [
            if (controller.busy && controller.phase != UploadPhase.uploading)
              const LinearProgressIndicator(),
            if (controller.error case final message?
                when controller.phase == UploadPhase.editing) ...[
              const SizedBox(height: 12),
              _message(message),
            ],
            const SizedBox(height: 12),
            ..._panel(context),
          ]),
        ),
      );
}
