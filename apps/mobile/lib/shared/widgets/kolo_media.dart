import 'package:flutter/material.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../features/creators/live_creator_repository.dart';
import '../../features/discovery/live_video_repository.dart';
import 'kolo_components.dart';

/// Image source for API-supplied posters. Production always loads the signed
/// URL from the network; tests and the design audit may substitute a local
/// fixture so populated states can be captured without network access.
@visibleForTesting
ImageProvider Function(Uri url)? posterProviderOverride;

ImageProvider posterProvider(Uri url) =>
    posterProviderOverride?.call(url) ?? NetworkImage(url.toString());

class KoloPoster extends StatelessWidget {
  const KoloPoster({super.key, required this.url, this.iconSize = 28});
  final Uri? url;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    final fallback = DecoratedBox(
      decoration: const BoxDecoration(
          gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [KoloVibeColors.navy, KoloVibeColors.deepNavy])),
      child: Center(
          child: Icon(Icons.play_circle_outline,
              color: Colors.white54, size: iconSize)),
    );
    if (url == null) return fallback;
    return Image(
        image: posterProvider(url!),
        fit: BoxFit.cover,
        excludeFromSemantics: true,
        errorBuilder: (_, __, ___) => fallback,
        loadingBuilder: (_, child, progress) =>
            progress == null ? child : fallback);
  }
}

class KoloHeroCard extends StatelessWidget {
  const KoloHeroCard(
      {super.key,
      required this.video,
      required this.meta,
      required this.onTap,
      this.eyebrow = 'KOLOVIBE ORIGINAL',
      this.minHeight = 212});
  final LiveVideo video;
  final String meta, eyebrow;
  final double minHeight;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: 'Play ${video.title}. $meta',
        excludeSemantics: true,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(KoloVibeRadii.card),
          child: Material(
            color: KoloVibeColors.navy,
            child: InkWell(
              onTap: onTap,
              child: Stack(children: [
                Positioned.fill(child: KoloPoster(url: video.posterUrl)),
                const Positioned.fill(
                    child: DecoratedBox(
                        decoration: BoxDecoration(
                            gradient: LinearGradient(
                                begin: Alignment.topCenter,
                                end: Alignment.bottomCenter,
                                colors: [
                      Color(0x21001539),
                      Color(0xF5001539)
                    ])))),
                ConstrainedBox(
                  constraints: BoxConstraints(minHeight: minHeight),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(18, 72, 18, 18),
                    child: Column(
                        mainAxisAlignment: MainAxisAlignment.end,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(eyebrow,
                              style: KoloVibeText.body(10,
                                  weight: FontWeight.w700,
                                  color: KoloVibeColors.gold,
                                  letterSpacing: 0.6)),
                          const SizedBox(height: 8),
                          Text(video.title,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: KoloVibeText.heading(27,
                                  color: Colors.white, height: 1.15)),
                          const SizedBox(height: 8),
                          Text(meta,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: KoloVibeText.body(11,
                                  color: Colors.white, height: 1.48)),
                        ]),
                  ),
                ),
                Positioned(
                  top: 16,
                  right: 18,
                  child: Container(
                    width: 42,
                    height: 42,
                    decoration: const BoxDecoration(
                        color: Colors.white, shape: BoxShape.circle),
                    child: const Icon(Icons.play_arrow_rounded,
                        color: KoloVibeColors.navy, size: 26),
                  ),
                ),
              ]),
            ),
          ),
        ),
      );
}

class KoloCreatorRow extends StatelessWidget {
  const KoloCreatorRow(
      {super.key,
      required this.creator,
      this.following,
      this.busy = false,
      required this.onOpen,
      this.onFollow,
      this.actionLabel,
      this.showBio = false});
  final LiveCreator creator;
  final String? actionLabel;
  final bool showBio;
  final bool? following;
  final bool busy;
  final VoidCallback onOpen;
  final VoidCallback? onFollow;

  @override
  Widget build(BuildContext context) {
    final name = creator.displayName.isEmpty
        ? '@${creator.handle}'
        : creator.displayName;
    final detail = [
      if (creator.displayName.isNotEmpty) '@${creator.handle}',
      if (creator.location.isNotEmpty) creator.location,
    ].join(' · ');
    final row = Row(children: [
      Expanded(
        child: Semantics(
          button: true,
          label: 'Open $name',
          excludeSemantics: true,
          child: InkWell(
            borderRadius: BorderRadius.circular(KoloVibeRadii.tile),
            onTap: onOpen,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 48),
              child: Row(children: [
                KoloAvatar(name: name, size: 44),
                const SizedBox(width: 12),
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      Text(name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.body(16,
                              weight: FontWeight.w600,
                              color: KoloVibeColors.navy,
                              height: 1.3)),
                      if (detail.isNotEmpty)
                        Text(detail,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: KoloVibeText.body(12, height: 1.3)),
                    ])),
              ]),
            ),
          ),
        ),
      ),
      const SizedBox(width: 8),
      KoloPillButton(
        label: actionLabel ?? (following == true ? 'Following' : 'Follow'),
        selected: actionLabel == null && following == true,
        semanticLabel: actionLabel != null
            ? '$actionLabel $name'
            : '${following == true ? 'Unfollow' : 'Follow'} $name',
        onPressed: busy ? null : onFollow,
      ),
    ]);
    if (!showBio || creator.bio.isEmpty) return row;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      row,
      Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Text(creator.bio,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: KoloVibeText.body(12, height: 1.5)),
      ),
    ]);
  }
}

class KoloVideoRow extends StatelessWidget {
  const KoloVideoRow(
      {super.key,
      this.kicker,
      required this.video,
      required this.meta,
      required this.onTap});
  final String? kicker;
  final String meta;
  final LiveVideo video;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: '${video.title}. $meta',
        excludeSemantics: true,
        child: InkWell(
          borderRadius: BorderRadius.circular(KoloVibeRadii.tile),
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 76),
            child: Row(children: [
              ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: SizedBox(
                      width: 104,
                      height: 76,
                      child: KoloPoster(url: video.posterUrl, iconSize: 22))),
              const SizedBox(width: 12),
              Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    if (kicker != null)
                      Text(kicker!,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.body(10,
                              weight: FontWeight.w600,
                              color: KoloVibeColors.red,
                              height: 1.48,
                              letterSpacing: 0.4)),
                    Text(video.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: KoloVibeText.body(14,
                            weight: FontWeight.w600,
                            color: KoloVibeColors.navy,
                            height: 1.35)),
                    if (meta.isNotEmpty)
                      Text(meta,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.body(11, height: 1.48)),
                  ])),
            ]),
          ),
        ),
      );
}

/// Two-up grid card: poster, title and meta line (M-019 "Fresh perspectives",
/// M-027 creator videos).
class KoloVideoCard extends StatelessWidget {
  const KoloVideoCard(
      {super.key,
      required this.video,
      required this.meta,
      required this.onTap,
      this.posterHeight = 92,
      this.titleSize = 12});
  final LiveVideo video;
  final String meta;
  final VoidCallback onTap;
  final double posterHeight, titleSize;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: '${video.title}. $meta',
        excludeSemantics: true,
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: onTap,
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            ClipRRect(
                borderRadius:
                    BorderRadius.circular(posterHeight > 100 ? 16 : 14),
                child: SizedBox(
                    height: posterHeight,
                    width: double.infinity,
                    child: KoloPoster(url: video.posterUrl, iconSize: 28))),
            const SizedBox(height: 6),
            Text(video.title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: KoloVibeText.body(titleSize,
                    weight: FontWeight.w600,
                    color: KoloVibeColors.navy,
                    height: 1.3)),
            if (meta.isNotEmpty)
              Text(meta,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: KoloVibeText.body(10, height: 1.4)),
          ]),
        ),
      );
}
