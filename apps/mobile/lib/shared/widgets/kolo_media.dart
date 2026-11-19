import 'package:flutter/material.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../features/creators/live_creator_repository.dart';
import '../../features/discovery/live_video_repository.dart';
import 'kolo_components.dart';

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
    return Image.network(url.toString(),
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
      required this.onTap});
  final LiveVideo video;
  final String meta;
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
                  constraints: const BoxConstraints(minHeight: 212),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(18, 72, 18, 18),
                    child: Column(
                        mainAxisAlignment: MainAxisAlignment.end,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('KOLOVIBE ORIGINAL',
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
      this.onFollow});
  final LiveCreator creator;
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
    return Row(children: [
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
        label: following == true ? 'Following' : 'Follow',
        selected: following == true,
        semanticLabel: '${following == true ? 'Unfollow' : 'Follow'} $name',
        onPressed: busy ? null : onFollow,
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
            constraints: const BoxConstraints(minHeight: 60),
            child: Row(children: [
              ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: SizedBox(
                      width: 80,
                      height: 60,
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
                        style: KoloVibeText.body(13,
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
