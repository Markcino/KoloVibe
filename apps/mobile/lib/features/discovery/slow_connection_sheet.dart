import 'package:flutter/material.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';

/// M-034 as adapted for R1 (D-3): the truthful slow-connection state.
///
/// KoloVibe plays one rendition in this release, so there is no Data Saver switch and nothing here
/// says playback changes quality. The sheet explains that the video is still loading, gives
/// connection guidance, and offers Try again and Keep waiting.
class SlowConnectionSheet extends StatelessWidget {
  const SlowConnectionSheet(
      {super.key,
      required this.onRetry,
      required this.onKeepWaiting,
      this.inline = false});
  final VoidCallback onRetry, onKeepWaiting;

  /// Drawn as a card inside a page (the video detail screen) instead of a bottom sheet.
  final bool inline;

  @override
  Widget build(BuildContext context) => Semantics(
        container: true,
        liveRegion: true,
        label: 'Your connection is slow',
        child: Material(
          color: KoloVibeColors.lavender,
          borderRadius: inline
              ? BorderRadius.circular(KoloVibeRadii.card)
              : const BorderRadius.vertical(top: Radius.circular(28)),
          child: SafeArea(
            top: false,
            minimum: const EdgeInsets.only(bottom: 8),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(24, 12, 24, 8),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (!inline)
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Container(
                          width: 40,
                          height: 4,
                          margin: const EdgeInsets.only(bottom: 16),
                          decoration: BoxDecoration(
                              color: KoloVibeColors.line,
                              borderRadius: BorderRadius.circular(2))),
                    ),
                  const KoloHeadline('Your connection is slow.', size: 24),
                  const SizedBox(height: 12),
                  Text(
                      'This video is taking longer than usual to start. It keeps loading, and you can try again at any time.',
                      style: KoloVibeText.body(14, height: 1.5)),
                  const SizedBox(height: 16),
                  const KoloNote(
                      title: 'Using MTN or Orange?',
                      message:
                          'Normal carrier data charges apply. Try a stronger signal, or switch between Wi-Fi and mobile data. This release plays one video quality.',
                      asset: KoloIcons.info),
                  FilledButton(
                      onPressed: onRetry, child: const Text('Try again')),
                  const SizedBox(height: 4),
                  TextButton(
                      onPressed: onKeepWaiting,
                      style: TextButton.styleFrom(
                          minimumSize: const Size.fromHeight(48),
                          textStyle:
                              KoloVibeText.body(14, weight: FontWeight.w700)),
                      child: const Text('Keep waiting')),
                ],
              ),
            ),
          ),
        ),
      );
}
