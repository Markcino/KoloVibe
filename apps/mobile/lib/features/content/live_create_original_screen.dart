import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../creators/live_creator_onboarding_repository.dart';
import 'live_content_repository.dart';
import 'live_upload_controller.dart';

class LiveCreateOriginalScreen extends StatefulWidget {
  const LiveCreateOriginalScreen(
      {super.key, required this.content, required this.onboarding});

  final LiveContentRepository content;
  final LiveCreatorOnboardingRepository onboarding;

  @override
  State<LiveCreateOriginalScreen> createState() =>
      _LiveCreateOriginalScreenState();
}

class _LiveCreateOriginalScreenState extends State<LiveCreateOriginalScreen> {
  late final LiveUploadController controller;
  final title = TextEditingController();
  final description = TextEditingController();

  @override
  void initState() {
    super.initState();
    controller = LiveUploadController(widget.content, widget.onboarding)
      ..addListener(_refresh);
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
    super.dispose();
  }

  Future<void> _select() async {
    try {
      final file = await ImagePicker().pickVideo(source: ImageSource.gallery);
      if (file != null) await controller.select(file);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('The video picker could not open. Try again.')));
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Create an original')),
        body: SafeArea(
          child: ListView(padding: const EdgeInsets.all(20), children: [
            if (controller.busy) const LinearProgressIndicator(),
            if (controller.error case final message?) ...[
              const SizedBox(height: 12),
              Semantics(liveRegion: true, child: Text(message)),
            ],
            if (controller.eligibility == null) ...[
              const SizedBox(height: 16),
              const Text('Checking creator access…'),
              if (!controller.busy)
                OutlinedButton(
                    onPressed: controller.checkEligibility,
                    child: const Text('Retry creator access')),
            ] else if (controller.eligibility!.eligible != true) ...[
              const SizedBox(height: 16),
              const Text('Creator upload is not available for this account.'),
              OutlinedButton(
                  onPressed:
                      controller.busy ? null : controller.checkEligibility,
                  child: const Text('Check again')),
            ] else ...[
              const Text('Select an MP4 original under 50 MB.'),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: controller.busy || controller.draft != null
                    ? null
                    : _select,
                icon: const Icon(Icons.video_library_outlined),
                label: const Text('Select video'),
              ),
              if (controller.selected case final file?)
                Text('${file.name} · ${controller.selectedBytes} bytes'),
              const SizedBox(height: 16),
              TextField(
                controller: title,
                enabled: !controller.busy && controller.draft == null,
                maxLength: 160,
                decoration: const InputDecoration(labelText: 'Title'),
              ),
              TextField(
                controller: description,
                enabled: !controller.busy && controller.draft == null,
                maxLength: 2000,
                maxLines: 4,
                decoration: const InputDecoration(labelText: 'Description'),
              ),
              if (controller.status case final status?) ...[
                Semantics(
                    liveRegion: true,
                    child: Text('Video status: ${status.state}')),
                const Text(
                    'The service will process and review your original before publication.'),
              ] else
                FilledButton(
                  onPressed: controller.busy || controller.selected == null
                      ? null
                      : () => controller.submit(title.text, description.text),
                  child: Text(controller.draft == null
                      ? 'Create and upload'
                      : 'Retry upload'),
                ),
              if (controller.draft case final draft?)
                Text('Draft: ${draft.title}'),
            ],
          ]),
        ),
      );
}
