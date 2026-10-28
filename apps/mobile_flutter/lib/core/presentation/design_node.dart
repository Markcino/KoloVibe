import 'package:flutter/services.dart';
import 'dart:convert';

/// Presentation data translated from inspected Figma nodes, never executable UI code.
class DesignNode {
  DesignNode.fromJson(Map<String, dynamic> json)
      : kind = json['kind'] as String,
        name = json['name'] as String? ?? '',
        id = json['id'] as String? ?? '',
        text = json['text'] as String? ?? '',
        asset = json['asset'] as String?,
        action = json['action'] as String?,
        style = Map<String, dynamic>.from(json['style'] as Map? ?? {}),
        children = (json['children'] as List? ?? [])
            .map((value) => DesignNode.fromJson(value as Map<String, dynamic>))
            .toList(growable: false);

  final String kind, name, id, text;
  final String? asset, action;
  final Map<String, dynamic> style;
  final List<DesignNode> children;
  double? dimension(String key) => (style[key] as num?)?.toDouble();
  String get label => [
        text,
        ...children.map((n) => n.label),
      ].where((text) => text.isNotEmpty).join(' ');
  Iterable<DesignNode> get descendants sync* {
    yield this;
    for (final child in children) {
      yield* child.descendants;
    }
  }
}

class DesignScreen {
  DesignScreen.fromJson(Map<String, dynamic> json)
      : number = json['number'] as int,
        name = json['name'] as String,
        figmaNode = json['node'] as String,
        root = DesignNode.fromJson(json['root'] as Map<String, dynamic>);
  final int number;
  final String name, figmaNode;
  final DesignNode root;
  DesignNode? named(String name) {
    for (final node in root.descendants) {
      if (node.name == name) return node;
    }
    return null;
  }

  bool get hasNavigation => named('Primary navigation') != null;
  bool get isDark =>
      (root.style['background'] as int? ?? 0xfff0f3ff) == 0xff001539;
}

class DesignCatalog {
  const DesignCatalog(this.screens);
  final Map<int, DesignScreen> screens;
  DesignScreen operator [](int id) => screens[id]!;

  static Future<DesignCatalog> load() async {
    final groups = await Future.wait([
      for (final group in [
        'account',
        'discovery',
        'studio',
        'points',
        'moderation',
        'settings',
        'states',
      ])
        rootBundle.loadString('assets/design/$group.json'),
    ]);
    final screens = <int, DesignScreen>{};
    for (final group in groups) {
      for (final json in jsonDecode(group) as List) {
        final screen = DesignScreen.fromJson(json as Map<String, dynamic>);
        screens[screen.number] = screen;
      }
    }
    if (screens.length != 108) {
      throw StateError('Incomplete mobile design catalog');
    }
    return DesignCatalog(Map.unmodifiable(screens));
  }
}
