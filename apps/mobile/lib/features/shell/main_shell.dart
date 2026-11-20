import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';

class MainShell extends StatelessWidget {
  const MainShell({
    super.key,
    required this.navigation,
    required this.screen,
    required this.onSelected,
  });
  final DesignNode navigation;
  final int screen;
  final ValueChanged<int> onSelected;
  static const targets = [17, 19, 37, 24, 79];
  static const labels = ['Home', 'Explore', 'Create', 'Videos', 'Profile'];
  @override
  Widget build(BuildContext context) {
    final surface = Color(navigation.style['background'] as int? ?? 0xffffffff);
    final inactive = surface == Colors.white
        ? KoloVibeColors.muted
        : const Color(0xffa8b7d0);
    final icons = navigation.children
        .where((n) => n.children.any((c) => c.kind == 'image'))
        .toList();
    final fallback = screen == 17
        ? 0
        : screen >= 37 && screen <= 60
            ? 2
            : screen >= 79 && screen <= 94
                ? 4
                : {18, 24, 25, 29, 30, 32, 33, 34, 70}.contains(screen)
                    ? 3
                    : 1;
    final designed = navigation.children
        .where((n) => n.kind == 'text')
        .toList()
        .indexWhere((n) => n.style['color'] == 0xffe02736);
    final selected = designed < 0 ? fallback : designed;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: surface,
        border: const Border(top: BorderSide(color: Color(0xffdae3f7))),
      ),
      child: SafeArea(
        top: false,
        child: Row(
          children: [
            for (var i = 0; i < 5; i++)
              Expanded(
                child: Semantics(
                  selected: selected == i,
                  button: true,
                  child: InkWell(
                    onTap: () => onSelected(targets[i]),
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(0, 10, 0, 4),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (icons.length > i &&
                              icons[i].children.first.asset != null)
                            SvgPicture.asset(
                              icons[i].children.first.asset!,
                              width: 24,
                              height: 24,
                              excludeFromSemantics: true,
                              colorFilter: ColorFilter.mode(
                                selected == i ? KoloVibeColors.red : inactive,
                                BlendMode.srcIn,
                              ),
                            )
                          else
                            Icon(
                              [
                                Icons.home_outlined,
                                Icons.explore_outlined,
                                Icons.add_circle_outline,
                                Icons.smart_display_outlined,
                                Icons.person_outline,
                              ][i],
                              color:
                                  selected == i ? KoloVibeColors.red : inactive,
                            ),
                          const SizedBox(height: 5),
                          // Labels keep the design's 10 px size; very large text
                          // settings would otherwise push the bar off screen.
                          MediaQuery.withClampedTextScaling(
                            maxScaleFactor: 1.3,
                            child: Text(
                              labels[i],
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: KoloVibeText.body(
                                10,
                                weight: selected == i
                                    ? FontWeight.w700
                                    : FontWeight.w500,
                                color: selected == i
                                    ? KoloVibeColors.red
                                    : inactive,
                                height: 1.2,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
