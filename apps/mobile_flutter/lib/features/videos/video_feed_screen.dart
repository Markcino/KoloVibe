import 'package:flutter/material.dart';
import '../../core/theme/kolovibe_theme.dart';

class VideoFeedScreen extends StatefulWidget {
  const VideoFeedScreen({super.key});

  @override
  State<VideoFeedScreen> createState() => _VideoFeedScreenState();
}

class _VideoFeedScreenState extends State<VideoFeedScreen> {
  bool following = false;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: KoloVibeColors.deepNavy,
      child: Stack(
        children: [
          Center(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 35),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.smart_display_outlined, color: Colors.white54, size: 62),
                  const SizedBox(height: 20),
                  Text('Original video lives here.', style: Theme.of(context).textTheme.titleLarge?.copyWith(color: Colors.white), textAlign: TextAlign.center),
                  const SizedBox(height: 10),
                  const Text('The full-screen video feed will open when published originals are available.', style: TextStyle(color: Color(0xFFC9D8EC), height: 1.5), textAlign: TextAlign.center),
                ],
              ),
            ),
          ),
          Positioned(
            top: 22,
            left: 0,
            right: 0,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _FeedTab(title: 'Following', selected: following, onTap: () => setState(() => following = true)),
                const SizedBox(width: 25),
                _FeedTab(title: 'For You', selected: !following, onTap: () => setState(() => following = false)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _FeedTab extends StatelessWidget {
  const _FeedTab({required this.title, required this.selected, required this.onTap});
  final String title;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(title, style: TextStyle(color: selected ? Colors.white : Colors.white70, fontWeight: selected ? FontWeight.w800 : FontWeight.w500)),
          const SizedBox(height: 8),
          Container(height: 3, width: 45, decoration: BoxDecoration(color: selected ? KoloVibeColors.red : Colors.transparent, borderRadius: BorderRadius.circular(3))),
        ],
      ),
    );
  }
}
