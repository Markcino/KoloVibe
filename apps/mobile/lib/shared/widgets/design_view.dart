import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../core/presentation/design_node.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../features/shell/screen_controller.dart';

typedef DesignAction = void Function(String action);

/// Native, adaptive widgets shared by the feature presentation recipes.
/// Numeric layout data is imported from Figma; no HTML, CSS or screenshots run here.
class DesignView extends StatelessWidget {
  const DesignView({
    super.key,
    required this.node,
    required this.controller,
    required this.onAction,
    this.inRow = false,
  });
  final DesignNode node;
  final ScreenController controller;
  final DesignAction onAction;
  final bool inRow;

  Widget child(DesignNode n, {bool row = false}) => DesignView(
        key: n.id.isEmpty ? null : ValueKey(n.id),
        node: n,
        controller: controller,
        onAction: onAction,
        inRow: row,
      );

  Color? color(String key) =>
      node.style[key] == null ? null : Color(node.style[key] as int);

  TextStyle get textStyle => TextStyle(
        fontFamily: node.style['family'] as String?,
        fontSize: node.dimension('fontSize'),
        color: color('color'),
        fontWeight: node.style['weight'] == null
            ? null
            : FontWeight.values[(node.style['weight'] as int) ~/ 100 - 1],
        fontVariations: node.style['weight'] == null
            ? null
            : [FontVariation('wght', (node.style['weight'] as num).toDouble())],
        height: node.dimension('lineHeight'),
      );

  @override
  Widget build(BuildContext context) {
    if (node.name == 'Primary navigation') return const SizedBox.shrink();
    if (node.name == 'Form field') return _field(context);
    if (node.name == 'Verification code') {
      return TextFormField(
        key: const ValueKey('verificationCode'),
        decoration: const InputDecoration(
          labelText: 'Verification code',
          counterText: '',
        ),
        keyboardType: TextInputType.text,
        maxLength: 128,
        autofillHints: const [AutofillHints.oneTimeCode],
        style: const TextStyle(fontSize: 16),
        onChanged: (v) => controller.update('verificationCode', v),
        validator: (v) => v != null && v.length >= 32
            ? null
            : 'Enter the verification code from your email.',
      );
    }
    if (node.name == 'Report text area') {
      return TextFormField(
        decoration: const InputDecoration(
          labelText: 'Additional details · Optional',
        ),
        maxLines: 4,
        maxLength: 2000,
        onChanged: (v) => controller.update('reportDetails', v),
      );
    }
    if (node.name == 'Search field') return _search();
    if (node.name == 'Action button') return _button();
    if (node.name == 'Preference row') return _preference();
    if (node.name == 'Filter chip' || node.name == 'Category filter') {
      return _chip();
    }
    if (node.name == 'Settings row' &&
        node.action?.startsWith('reason:') == true) {
      final selected = controller.reason == node.label;
      return RadioGroup<String>(
        groupValue: controller.reason,
        onChanged: (value) {
          if (value != null) controller.choose(value, report: true);
        },
        child: Material(
            type: MaterialType.transparency,
            child: RadioListTile<String>(
              contentPadding: EdgeInsets.zero,
              value: node.label,
              activeColor: KoloVibeColors.red,
              title: Text(node.label, style: const TextStyle(fontSize: 14)),
              selected: selected,
            )),
      );
    }
    if (node.name == 'Feed switcher') {
      return Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          for (final entry in const {'Following': 18, 'For You': 24}.entries)
            TextButton(
              onPressed: () => onAction('go:${entry.value}'),
              child: Text(
                entry.key,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
        ],
      );
    }
    if (node.children.any((n) => n.name == 'square-check')) {
      return Material(
          type: MaterialType.transparency,
          child: CheckboxListTile(
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            value: controller.acknowledged,
            title: Text(node.label, style: const TextStyle(fontSize: 12)),
            onChanged: (v) => controller.acknowledge(v ?? false),
          ));
    }

    Widget result;
    if (node.kind == 'image') {
      final asset = node.asset;
      result = asset == null
          ? const SizedBox.shrink()
          : asset.endsWith('.svg')
              ? SvgPicture.asset(
                  asset,
                  fit: BoxFit.contain,
                  excludeFromSemantics: true,
                )
              : Image.asset(asset,
                  fit: BoxFit.cover, excludeFromSemantics: true);
    } else if (node.kind == 'text') {
      final align = node.style['textAlign'];
      final textAlign = align == 'center'
          ? TextAlign.center
          : align == 'right'
              ? TextAlign.right
              : TextAlign.start;
      result = node.text.contains('☀')
          ? Text.rich(
              TextSpan(children: [
                TextSpan(text: node.text.split('☀').first),
                WidgetSpan(
                    alignment: PlaceholderAlignment.middle,
                    child: Icon(Icons.wb_sunny_rounded,
                        color: const Color(0xffffba24),
                        size: textStyle.fontSize ?? 24)),
              ]),
              style: textStyle,
              textAlign: textAlign,
            )
          : Text(node.text, style: textStyle, textAlign: textAlign);
    } else if (node.kind == 'wrap') {
      result = Wrap(
        spacing: node.dimension('gap') ?? 8,
        runSpacing: node.dimension('gap') ?? 8,
        children: node.children.map(child).toList(),
      );
    } else if (node.kind == 'stack') {
      result = _stack(context);
    } else if (node.kind == 'row') {
      result = _row(context);
    } else if (node.children.isNotEmpty) {
      final gap = node.dimension('gap') ?? 0;
      // A fixed-height column with `main: center` (for example the round play
      // button) centres its content vertically, as drawn in the design.
      final centered =
          node.style['main'] == 'center' && node.dimension('height') != null;
      result = Column(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment:
            centered ? MainAxisAlignment.center : MainAxisAlignment.start,
        crossAxisAlignment: _cross(node.style['cross']),
        children: [
          if (node.text.isNotEmpty) Text(node.text),
          for (var i = 0; i < node.children.length; i++) ...[
            if (i > 0 && gap > 0) SizedBox(height: gap),
            child(node.children[i]),
          ],
        ],
      );
    } else {
      result = const SizedBox.shrink();
    }

    if (node.kind != 'text' && node.kind != 'image') {
      result = DefaultTextStyle.merge(style: textStyle, child: result);
    }
    result = _decoration(result);
    final action = node.action;
    if (action != null) {
      result = Semantics(
        button: true,
        label: action == 'back'
            ? 'Back'
            : node.label.isEmpty
                ? node.name
                : null,
        child: InkWell(
          onTap: controller.busy ? null : () => onAction(action),
          borderRadius: BorderRadius.circular(node.dimension('radius') ?? 12),
          child: result,
        ),
      );
    }
    return result;
  }

  static CrossAxisAlignment _cross(dynamic value) => value == 'center'
      ? CrossAxisAlignment.center
      : value == 'end'
          ? CrossAxisAlignment.end
          : CrossAxisAlignment.start;

  Widget _row(BuildContext context) {
    final gap = node.dimension('gap') ?? 0;
    if (node.name == 'KoloVibe wordmark') {
      return Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            for (var i = 0; i < node.children.length; i++) ...[
              if (i > 0) SizedBox(width: gap),
              child(node.children[i]),
            ]
          ]);
    }
    return LayoutBuilder(
      builder: (context, constraints) {
        final accessible = MediaQuery.textScalerOf(context).scale(1) > 1.3;
        if (accessible &&
            {
              'Section heading',
              'Platform services',
              'Content row',
              'Creator identity',
              'Discovery grid',
              'Video catalog'
            }.contains(node.name)) {
          return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                for (var i = 0; i < node.children.length; i++) ...[
                  if (i > 0) SizedBox(height: gap),
                  child(node.children[i]),
                ]
              ]);
        }
        final children = <Widget>[];
        for (var i = 0; i < node.children.length; i++) {
          final n = node.children[i];
          if (i > 0 && gap > 0) children.add(SizedBox(width: gap));
          final flexible = n.style['flex'] == true ||
              n.style['fill'] == true ||
              (n.kind == 'text' &&
                  n.dimension('width') == null &&
                  node.children.length > 1 &&
                  node.style['main'] != 'between') ||
              (n.dimension('width') ?? 0) > 240;
          children.add(
            flexible && constraints.hasBoundedWidth
                ? Expanded(child: child(n, row: true))
                : child(n, row: true),
          );
        }
        return Row(
          mainAxisSize: MainAxisSize.max,
          mainAxisAlignment: node.style['main'] == 'between'
              ? MainAxisAlignment.spaceBetween
              : node.style['main'] == 'center'
                  ? MainAxisAlignment.center
                  : MainAxisAlignment.start,
          crossAxisAlignment: _cross(node.style['cross']),
          children: children,
        );
      },
    );
  }

  Widget _stack(BuildContext context) {
    // Absolute composition is confined to image captions, charts and player chrome.
    final width = node.dimension('width') ?? 342;
    final height = node.dimension('height') ?? 220;
    return LayoutBuilder(
      builder: (context, constraints) {
        final actualWidth = constraints.hasBoundedWidth
            ? math.min(width, constraints.maxWidth)
            : width;
        final scale = actualWidth / width;
        final textScale = MediaQuery.textScalerOf(context).scale(1);
        return SizedBox(
          width: actualWidth,
          height: height *
              (node.children.any(
                      (n) => n.kind == 'text' || n.name == 'Feature caption')
                  ? math.max(1, textScale * .85)
                  : 1),
          child: Stack(
            clipBehavior: Clip.hardEdge,
            children: [
              for (final n in node.children)
                if (n.kind == 'image')
                  Positioned.fill(child: child(n))
                else if (n.style['positioned'] == true)
                  Positioned(
                    left: (n.dimension('x') ?? 0) * scale -
                        (n.style['centerX'] == true
                            ? (n.dimension('width') ?? 0) * scale / 2
                            : 0),
                    top: n.dimension('y'),
                    width: n.dimension('width') == null
                        ? actualWidth
                        : math.min(n.dimension('width')! * scale, actualWidth),
                    child: child(n),
                  )
                else
                  Positioned.fill(child: child(n)),
            ],
          ),
        );
      },
    );
  }

  Widget _decoration(Widget result) {
    final s = node.style;
    final p =
        (s['padding'] as List?)?.map((v) => (v as num).toDouble()).toList();
    final padding = p == null
        ? EdgeInsets.zero
        : EdgeInsets.fromLTRB(p[0], p[1], p[2], p[3]);
    final radius = node.dimension('radius') ?? 0;
    final topRadius = node.dimension('topRadius');
    final width = node.dimension('width');
    final height = node.dimension('height');
    final isText = node.kind == 'text';
    // Text and content containers grow with accessibility text size.
    final fixedHeight = node.kind == 'image' ||
        node.children.isEmpty ||
        [
          'Original artwork',
          'Frame choice',
          'Feature skeleton',
        ].contains(node.name);
    final effectiveWidth = width != null && width < 300 && !inRow
        ? width
        : inRow && width != null && width < 240
            ? width
            : null;
    if (p == null &&
        color('background') == null &&
        color('borderColor') == null &&
        radius == 0 &&
        width == null &&
        height == null &&
        s['gradient'] != true) {
      return result;
    }
    return Container(
      width: effectiveWidth,
      height: !isText && fixedHeight ? height : null,
      constraints: BoxConstraints(
        minHeight: node.dimension('minHeight') ??
            (!isText && !fixedHeight ? height ?? 0 : 0),
      ),
      padding: padding,
      clipBehavior: radius > 0 ? Clip.antiAlias : Clip.none,
      decoration: BoxDecoration(
        color: color('background'),
        gradient: s['gradient'] == true
            ? LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  color('gradientFrom') ?? Colors.transparent,
                  color('gradientTo') ?? KoloVibeColors.deepNavy,
                ],
              )
            : null,
        border: color('borderColor') == null
            ? null
            : Border.all(color: color('borderColor')!),
        borderRadius: topRadius != null
            ? BorderRadius.vertical(top: Radius.circular(topRadius))
            : BorderRadius.circular(radius),
      ),
      child: result,
    );
  }

  Widget _button() {
    final disabled = node.label.toLowerCase().contains('unavailable');
    final background = color('background') ?? KoloVibeColors.red;
    final foreground =
        background == KoloVibeColors.red || background == KoloVibeColors.navy
            ? Colors.white
            : KoloVibeColors.navy;
    return SizedBox(
      width: double.infinity,
      child: FilledButton(
        onPressed: disabled || controller.busy
            ? null
            : () => onAction(node.action ?? 'unavailable'),
        style: FilledButton.styleFrom(
          backgroundColor: background,
          foregroundColor: foreground,
          minimumSize: const Size(0, 50),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: controller.busy
            ? const SizedBox(
                height: 20,
                width: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : Text(
                node.label,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                ),
              ),
      ),
    );
  }

  Widget _chip() {
    final label = node.label == 'Rights or ownership concern' &&
            controller.reason.isNotEmpty
        ? controller.reason
        : node.label;
    final selectable = node.action?.startsWith('select:') == true;
    final selected = controller.selected == node.label;
    return Semantics(
      selected: selectable ? selected : null,
      child: ActionChip(
        disabledColor: color('background') ?? Colors.white,
        label: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: selected
                ? Colors.white
                : node.children.isNotEmpty
                    ? Color(
                        node.children.first.style['color'] as int? ??
                            0xff102a56,
                      )
                    : KoloVibeColors.navy,
          ),
        ),
        backgroundColor: selected
            ? KoloVibeColors.navy
            : color('background') ?? Colors.white,
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
        side: const BorderSide(color: Color(0xffdae3f7)),
        shape: const StadiumBorder(),
        onPressed: node.action == null ? null : () => onAction(node.action!),
      ),
    );
  }

  Widget _preference() => Material(
      type: MaterialType.transparency,
      child: SwitchListTile.adaptive(
        contentPadding: EdgeInsets.zero,
        title: Text(
          node.children.isEmpty ? node.label : node.children.first.label,
          style: const TextStyle(fontSize: 14),
        ),
        value: controller.fields[node.id] == 'true',
        onChanged: null,
      ));

  Widget _search() {
    final hint = node.children
        .where((n) => n.kind == 'text')
        .map((n) => n.text)
        .join(' ');
    return TextField(
      key: const ValueKey('search'),
      decoration: InputDecoration(
        isDense: true,
        contentPadding: const EdgeInsets.all(14),
        hintText: hint.isEmpty ? 'Search videos, creators…' : hint,
        prefixIcon: Padding(
            padding: const EdgeInsets.all(14),
            child: child(node.children.firstWhere((n) => n.name == 'search'))),
        suffixIcon: IconButton(
          tooltip: 'Search filters',
          icon: child(
              node.children.firstWhere((n) => n.name == 'sliders-horizontal')),
          onPressed: () => onAction('go:23'),
        ),
      ),
      textInputAction: TextInputAction.search,
      onChanged: (v) => controller.update('query', v),
      onSubmitted: (_) => onAction('search'),
    );
  }

  Widget _field(BuildContext context) {
    final texts = node.descendants.where((n) => n.kind == 'text').toList();
    final label = texts.isEmpty ? 'Details' : texts.first.text;
    final sensitive = label.toLowerCase().contains('password');
    final email = label.toLowerCase().contains('email');
    final multiline = label == 'Bio' || label == 'Description';
    if (label.contains('Category')) {
      return DropdownButtonFormField<String>(
        isExpanded: true,
        decoration: InputDecoration(labelText: label),
        items: [
          for (final category in const [
            'Hipco',
            'Afrobeats',
            'Comedy',
            'Skits',
            'Short films',
            'Culture',
            'Documentaries'
          ])
            DropdownMenuItem(value: category, child: Text(category))
        ],
        onChanged: (value) {
          if (value != null) controller.update(label, value);
        },
        validator: (value) =>
            value == null ? 'Select a category to continue.' : null,
      );
    }
    return DesignFormField(
      key: ValueKey(node.id),
      label: label,
      initialValue: '',
      sensitive: sensitive,
      email: email,
      multiline: multiline,
      controller: controller,
      passwordIcon:
          node.descendants.where((n) => n.name == 'eye-off').firstOrNull,
      onChanged: (value) => controller.update(label, value),
      onCategory:
          label.contains('Category') ? () => onAction('category') : null,
      validator: (value) {
        final text = value?.trim() ?? '';
        if (label.contains('DELETE') && text != 'DELETE') {
          return 'Type DELETE to acknowledge.';
        }
        if (text.isEmpty && !label.contains('Optional') && !multiline) {
          return 'Enter ${label.toLowerCase()}.';
        }
        if (email && !RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(text)) {
          return 'Enter a valid email address.';
        }
        if (label.toLowerCase().contains('confirm') && sensitive) {
          final password = controller.fields['New password'] ??
              controller.fields['Password'];
          if (value != password) return 'The passwords don’t match.';
        }
        if (label.contains('DELETE') && text != 'DELETE') {
          return 'Type DELETE to acknowledge.';
        }
        return null;
      },
    );
  }
}

class DesignFormField extends StatefulWidget {
  const DesignFormField({
    super.key,
    required this.label,
    required this.initialValue,
    required this.sensitive,
    required this.email,
    required this.multiline,
    required this.onChanged,
    required this.validator,
    required this.controller,
    this.passwordIcon,
    this.onCategory,
  });
  final ScreenController controller;
  final DesignNode? passwordIcon;
  final String label, initialValue;
  final bool sensitive, email, multiline;
  final ValueChanged<String> onChanged;
  final FormFieldValidator<String> validator;
  final VoidCallback? onCategory;
  @override
  State<DesignFormField> createState() => _DesignFormFieldState();
}

class _DesignFormFieldState extends State<DesignFormField> {
  late final TextEditingController editing;
  bool visible = false;
  @override
  void initState() {
    super.initState();
    editing = TextEditingController(text: widget.initialValue);
    if (widget.sensitive) {
      widget.controller.sensitiveClearers.add(editing.clear);
    }
    if (widget.initialValue.isNotEmpty) {
      widget.controller.fields[widget.label] = widget.initialValue;
    }
  }

  @override
  void dispose() {
    widget.controller.sensitiveClearers.remove(editing.clear);
    editing.clear();
    editing.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.label,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 7),
          TextFormField(
            controller: editing,
            obscureText: widget.sensitive && !visible,
            enableSuggestions: !widget.sensitive,
            autocorrect: !widget.sensitive,
            keyboardType: widget.email
                ? TextInputType.emailAddress
                : widget.multiline
                    ? TextInputType.multiline
                    : TextInputType.text,
            maxLines: widget.multiline ? 3 : 1,
            maxLength: widget.multiline ? 2000 : 254,
            decoration: InputDecoration(
              hintText: widget.sensitive
                  ? 'Enter ${widget.label.toLowerCase()}'
                  : widget.label,
              counterText: '',
              suffixIcon: widget.sensitive
                  ? IconButton(
                      tooltip: visible ? 'Hide password' : 'Show password',
                      icon: widget.passwordIcon == null
                          ? const Icon(Icons.visibility_outlined)
                          : SvgPicture.asset(
                              widget.passwordIcon!.children.first.asset!,
                              excludeFromSemantics: true),
                      onPressed: () => setState(() => visible = !visible),
                    )
                  : null,
            ),
            style: const TextStyle(fontSize: 14),
            validator: widget.validator,
            onChanged: widget.onChanged,
          ),
          if (widget.onCategory != null)
            TextButton(
              onPressed: widget.onCategory,
              child: const Text('Choose a category'),
            ),
        ],
      );
}
