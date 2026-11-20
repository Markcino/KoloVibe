import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../core/theme/kolovibe_theme.dart';

/// Brand emblem and wordmark used in the application header.
class KoloWordmark extends StatelessWidget {
  const KoloWordmark({super.key});

  @override
  Widget build(BuildContext context) => Semantics(
        header: true,
        label: 'KoloVibe',
        excludeSemantics: true,
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          SvgPicture.asset('assets/images/88dfdf7ffa8d70c62080.svg',
              width: 32, height: 32, excludeFromSemantics: true),
          const SizedBox(width: 9),
          Flexible(
              child: Text('KoloVibe',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: KoloVibeText.heading(22))),
        ]),
      );
}

/// Circular initial avatar. Accounts carry no profile photo, so the initial of
/// the real display name is used and nothing is invented.
class KoloAvatar extends StatelessWidget {
  const KoloAvatar(
      {super.key,
      required this.name,
      this.size = 44,
      this.onTap,
      this.semanticLabel});
  final String name;
  final double size;
  final VoidCallback? onTap;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    final initial = name.trim().isEmpty
        ? '?'
        : String.fromCharCode(name.trim().runes.first).toUpperCase();
    final avatar = Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: const BoxDecoration(
          color: KoloVibeColors.navy, shape: BoxShape.circle),
      child: Text(initial,
          style: KoloVibeText.heading(size * 0.42, color: Colors.white)),
    );
    return Semantics(
      label: semanticLabel ?? name,
      button: onTap != null,
      excludeSemantics: true,
      child: onTap == null
          ? avatar
          : InkResponse(
              onTap: onTap,
              radius: size / 2 + 8,
              child: ConstrainedBox(
                  constraints:
                      const BoxConstraints(minWidth: 44, minHeight: 44),
                  child: Center(child: avatar))),
    );
  }
}

/// Read-only search entry that opens the search screen when tapped.
class KoloSearchBar extends StatelessWidget {
  const KoloSearchBar(
      {super.key, required this.hint, required this.onTap, this.trailingTap});
  final String hint;
  final VoidCallback onTap;
  final VoidCallback? trailingTap;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: hint,
        excludeSemantics: true,
        child: Material(
          color: Colors.white,
          shape: RoundedRectangleBorder(
              side: const BorderSide(color: KoloVibeColors.line),
              borderRadius: BorderRadius.circular(KoloVibeRadii.field)),
          child: InkWell(
            borderRadius: BorderRadius.circular(KoloVibeRadii.field),
            onTap: onTap,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 50),
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                child: Row(children: [
                  SvgPicture.asset('assets/images/96a2f99af25ad7f6acca.svg',
                      width: 20, height: 20, excludeFromSemantics: true),
                  const SizedBox(width: 10),
                  Expanded(
                      child: Text(hint,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.body(13))),
                  const SizedBox(width: 10),
                  SvgPicture.asset('assets/images/84754de6e461aa4a37de.svg',
                      width: 18, height: 18, excludeFromSemantics: true),
                ]),
              ),
            ),
          ),
        ),
      );
}

/// Section title with an optional trailing action such as "See all".
class KoloSectionHeading extends StatelessWidget {
  const KoloSectionHeading(
      {super.key, required this.title, this.actionLabel, this.onAction});
  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) => Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
              child: Semantics(
                  header: true,
                  child: Text(title, style: KoloVibeText.heading(18)))),
          if (actionLabel != null && onAction != null)
            TextButton(
              onPressed: onAction,
              style: TextButton.styleFrom(
                  foregroundColor: KoloVibeColors.red,
                  minimumSize: const Size(44, 44),
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  textStyle: KoloVibeText.body(12, weight: FontWeight.w600)),
              child: Text(actionLabel!),
            ),
        ],
      );
}

/// White rounded shortcut tile with an icon above a label.
class KoloServiceTile extends StatelessWidget {
  const KoloServiceTile(
      {super.key,
      required this.asset,
      required this.label,
      required this.onTap});
  final String asset, label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: label,
        excludeSemantics: true,
        child: Material(
          color: Colors.white,
          borderRadius: BorderRadius.circular(KoloVibeRadii.tile),
          child: InkWell(
            borderRadius: BorderRadius.circular(KoloVibeRadii.tile),
            onTap: onTap,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 64),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SvgPicture.asset(asset,
                          width: 21, height: 21, excludeFromSemantics: true),
                      const SizedBox(height: 5),
                      Text(label,
                          textAlign: TextAlign.center,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: KoloVibeText.body(11,
                              weight: FontWeight.w700,
                              color: KoloVibeColors.navy)),
                    ]),
              ),
            ),
          ),
        ),
      );
}

/// Pill used for categories.
class KoloChip extends StatelessWidget {
  const KoloChip({super.key, required this.label, required this.onTap});
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: label,
        excludeSemantics: true,
        child: Material(
          color: Colors.white,
          shape:
              const StadiumBorder(side: BorderSide(color: KoloVibeColors.line)),
          child: InkWell(
            customBorder: const StadiumBorder(),
            onTap: onTap,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 44),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                child: Center(
                    widthFactor: 1,
                    child: Text(label,
                        style: KoloVibeText.body(12,
                            weight: FontWeight.w600,
                            color: KoloVibeColors.navy))),
              ),
            ),
          ),
        ),
      );
}

/// Filled navy pill button, such as Follow. [busy] disables it while a request
/// is in flight; [selected] switches to the outlined "Following" appearance.
class KoloPillButton extends StatelessWidget {
  const KoloPillButton(
      {super.key,
      required this.label,
      required this.onPressed,
      this.selected = false,
      this.semanticLabel});
  final String label;
  final VoidCallback? onPressed;
  final bool selected;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        enabled: onPressed != null,
        label: semanticLabel ?? label,
        excludeSemantics: true,
        child: Material(
          color: selected ? Colors.white : KoloVibeColors.navy,
          shape:
              const StadiumBorder(side: BorderSide(color: KoloVibeColors.line)),
          child: InkWell(
            customBorder: const StadiumBorder(),
            onTap: onPressed,
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 44, minWidth: 44),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 14),
                child: Center(
                    widthFactor: 1,
                    child: Text(label,
                        style: KoloVibeText.body(12,
                            weight: FontWeight.w600,
                            color: selected
                                ? KoloVibeColors.navy
                                : Colors.white))),
              ),
            ),
          ),
        ),
      );
}

/// Static placeholder block shown while a section loads.
class KoloSkeleton extends StatelessWidget {
  const KoloSkeleton(
      {super.key, this.width, required this.height, this.radius = 12});
  final double? width;
  final double height, radius;

  @override
  Widget build(BuildContext context) => Container(
      width: width,
      height: height,
      decoration: BoxDecoration(
          color: KoloVibeColors.softBlue,
          borderRadius: BorderRadius.circular(radius)));
}

/// Inline card for the empty, error and signed-out state of one dashboard
/// section. Each section owns its state, so one failure never hides the rest.
class KoloInlineState extends StatelessWidget {
  const KoloInlineState(
      {super.key,
      required this.title,
      required this.message,
      this.icon = Icons.info_outline,
      this.actionLabel,
      this.onAction});
  final String title, message;
  final IconData icon;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) => Semantics(
        container: true,
        liveRegion: true,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
              color: Colors.white,
              border: Border.all(color: KoloVibeColors.line),
              borderRadius: BorderRadius.circular(KoloVibeRadii.tile)),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(icon, color: KoloVibeColors.navy, size: 22),
            const SizedBox(width: 12),
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text(title,
                      style: KoloVibeText.body(14,
                          weight: FontWeight.w700, color: KoloVibeColors.navy)),
                  const SizedBox(height: 4),
                  Text(message, style: KoloVibeText.body(12, height: 1.4)),
                  if (actionLabel != null && onAction != null) ...[
                    const SizedBox(height: 8),
                    KoloPillButton(label: actionLabel!, onPressed: onAction),
                  ],
                ])),
          ]),
        ),
      );
}

/// Text field with its label above the box, as drawn in the approved designs.
/// Secret fields get the show/hide control. The whole widget carries [key], so
/// callers (and tests) can address a field by its label.
class KoloTextField extends StatefulWidget {
  const KoloTextField({
    super.key,
    required this.label,
    required this.controller,
    this.hint,
    this.helper,
    this.secret = false,
    this.readOnly = false,
    this.maxLength,
    this.keyboardType,
    this.autofillHints,
    this.onChanged,
    this.validator,
    this.textInputAction,
    this.onSubmitted,
    this.maxLines = 1,
  });
  final String label;
  final TextEditingController controller;
  final String? hint, helper;
  final bool secret, readOnly;
  final int? maxLength;
  final int maxLines;
  final TextInputType? keyboardType;
  final Iterable<String>? autofillHints;
  final ValueChanged<String>? onChanged;
  final FormFieldValidator<String>? validator;
  final TextInputAction? textInputAction;
  final ValueChanged<String>? onSubmitted;

  @override
  State<KoloTextField> createState() => _KoloTextFieldState();
}

class _KoloTextFieldState extends State<KoloTextField> {
  late bool hidden = widget.secret;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Text(widget.label,
                style: KoloVibeText.body(12,
                    weight: FontWeight.w600, color: KoloVibeColors.navy)),
          ),
          TextFormField(
            controller: widget.controller,
            readOnly: widget.readOnly,
            obscureText: hidden,
            maxLength: widget.maxLength,
            maxLines: widget.secret ? 1 : widget.maxLines,
            autocorrect: !widget.secret,
            enableSuggestions: !widget.secret,
            keyboardType: widget.keyboardType,
            autofillHints: widget.autofillHints,
            textInputAction: widget.textInputAction,
            onFieldSubmitted: widget.onSubmitted,
            onChanged: widget.onChanged,
            validator: widget.validator,
            // Read-only values (the account email) are drawn like any field.
            style: KoloVibeText.body(14, color: KoloVibeColors.ink),
            decoration: InputDecoration(
              hintText: widget.hint,
              counterText: '',
              fillColor: widget.readOnly ? Colors.white : null,
              suffixIcon: widget.secret
                  ? IconButton(
                      tooltip: hidden ? 'Show' : 'Hide',
                      onPressed: () => setState(() => hidden = !hidden),
                      icon: Icon(
                          hidden
                              ? Icons.visibility_off_outlined
                              : Icons.visibility_outlined,
                          size: 20,
                          color: KoloVibeColors.muted))
                  : null,
            ),
          ),
          if (widget.helper != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(widget.helper!, style: KoloVibeText.body(12)),
            ),
        ]),
      );
}

/// Large two-line display headline used at the top of form screens.
class KoloHeadline extends StatelessWidget {
  const KoloHeadline(this.text, {super.key, this.size = 28});
  final String text;
  final double size;

  @override
  Widget build(BuildContext context) => Semantics(
        header: true,
        child: Text(text, style: KoloVibeText.heading(size, height: 1.15)),
      );
}

/// Soft informational card: a bold title over explanatory text. [tone] picks
/// the approved tint (soft blue, mint, blush); [asset] draws a Figma icon
/// instead of the Material [icon].
class KoloNote extends StatelessWidget {
  const KoloNote(
      {super.key,
      required this.title,
      required this.message,
      this.icon = Icons.info_outline,
      this.asset,
      this.tone = KoloNoteTone.info});
  final String title, message;
  final IconData icon;
  final String? asset;
  final KoloNoteTone tone;

  @override
  Widget build(BuildContext context) {
    final color = switch (tone) {
      KoloNoteTone.info => KoloVibeColors.navy,
      KoloNoteTone.success => KoloVibeColors.green,
      KoloNoteTone.alert => KoloVibeColors.red,
    };
    final background = switch (tone) {
      KoloNoteTone.info => KoloVibeColors.softBlue,
      KoloNoteTone.success => const Color(0xFFE5F4EE),
      KoloNoteTone.alert => const Color(0xFFFCECEF),
    };
    return Semantics(
      container: true,
      liveRegion: tone != KoloNoteTone.info,
      child: Container(
        width: double.infinity,
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
            color: background,
            borderRadius: BorderRadius.circular(KoloVibeRadii.tile)),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          asset == null
              ? Icon(icon, size: 20, color: color)
              : ExcludeSemantics(
                  child: SvgPicture.asset(asset!, width: 20, height: 20)),
          const SizedBox(width: 12),
          Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text(title,
                    style: KoloVibeText.body(13,
                        weight: FontWeight.w600,
                        color: tone == KoloNoteTone.info
                            ? KoloVibeColors.navy
                            : color)),
                const SizedBox(height: 4),
                Text(message, style: KoloVibeText.body(12, height: 1.5)),
              ])),
        ]),
      ),
    );
  }
}

enum KoloNoteTone { info, success, alert }

/// Small status badge (for example "Creator enabled").
class KoloBadge extends StatelessWidget {
  const KoloBadge(this.label, {super.key, this.filled = false});
  final String label;
  final bool filled;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
        decoration: ShapeDecoration(
          color: filled ? KoloVibeColors.navy : Colors.white,
          shape:
              const StadiumBorder(side: BorderSide(color: KoloVibeColors.line)),
        ),
        child: Text(label,
            style: KoloVibeText.body(12,
                weight: FontWeight.w600,
                color: filled ? Colors.white : KoloVibeColors.navy)),
      );
}

/// Settings-style row: bold title, muted subtitle and a trailing icon, with a
/// hairline divider. [onTap] makes the whole row a button.
class KoloListRow extends StatelessWidget {
  const KoloListRow(
      {super.key,
      required this.title,
      this.subtitle,
      this.icon = Icons.chevron_right,
      this.onTap,
      this.divider = true,
      this.destructive = false});
  final String title;
  final String? subtitle;
  final IconData icon;
  final VoidCallback? onTap;
  final bool divider, destructive;

  @override
  Widget build(BuildContext context) => Semantics(
        button: onTap != null,
        child: InkWell(
          onTap: onTap,
          child: Container(
            constraints: const BoxConstraints(minHeight: 56),
            padding: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(
                border: divider
                    ? const Border(
                        bottom: BorderSide(color: KoloVibeColors.line))
                    : null),
            child: Row(children: [
              Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    Text(title,
                        style: KoloVibeText.body(15,
                            weight: FontWeight.w600,
                            color: destructive
                                ? KoloVibeColors.red
                                : KoloVibeColors.navy)),
                    if (subtitle != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(subtitle!, style: KoloVibeText.body(12)),
                      ),
                  ])),
              const SizedBox(width: 12),
              Icon(icon, size: 20, color: KoloVibeColors.muted),
            ]),
          ),
        ),
      );
}

/// Large statistic card: an icon, a display number and a caption. [dark] gives
/// the navy card with a gold number; otherwise a white card.
class KoloHeroStat extends StatelessWidget {
  const KoloHeroStat(
      {super.key,
      required this.value,
      required this.caption,
      this.icon = Icons.star_outline,
      this.eyebrow,
      this.dark = false});
  final String value, caption;
  final String? eyebrow;
  final IconData icon;
  final bool dark;

  @override
  Widget build(BuildContext context) => Semantics(
        container: true,
        child: Container(
          width: double.infinity,
          margin: const EdgeInsets.only(bottom: 16),
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
              color: dark ? KoloVibeColors.navy : Colors.white,
              borderRadius: BorderRadius.circular(KoloVibeRadii.card)),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(icon,
                size: 28,
                color: dark ? KoloVibeColors.gold : KoloVibeColors.navy),
            const SizedBox(height: 12),
            Text(value,
                style: KoloVibeText.heading(40,
                    color: dark ? KoloVibeColors.gold : KoloVibeColors.navy,
                    height: 1.1)),
            const SizedBox(height: 8),
            Text(caption,
                style: KoloVibeText.body(13,
                    color: dark ? Colors.white : KoloVibeColors.muted)),
          ]),
        ),
      );
}

/// Centred state layout used by the system states: an icon medallion, a small
/// label, a display headline, an explanation and its actions.
class KoloStatePanel extends StatelessWidget {
  const KoloStatePanel({
    super.key,
    required this.icon,
    required this.label,
    required this.headline,
    required this.message,
    this.note,
    this.actions = const [],
  });
  final IconData icon;
  final String label, headline, message;
  final Widget? note;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) => Semantics(
        liveRegion: true,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                    color: KoloVibeColors.softBlue,
                    borderRadius: BorderRadius.circular(20)),
                child: Icon(icon, size: 30, color: KoloVibeColors.navy),
              ),
            ),
            const SizedBox(height: 20),
            Text(label,
                textAlign: TextAlign.center,
                style: KoloVibeText.body(12,
                    weight: FontWeight.w600, color: KoloVibeColors.muted)),
            const SizedBox(height: 6),
            Text(headline,
                textAlign: TextAlign.center,
                style: KoloVibeText.heading(26, height: 1.15)),
            const SizedBox(height: 12),
            Text(message,
                textAlign: TextAlign.center,
                style: KoloVibeText.body(14, height: 1.5)),
            if (note != null) ...[const SizedBox(height: 16), note!],
            for (final action in actions) ...[
              const SizedBox(height: 12),
              action,
            ],
          ],
        ),
      );
}

/// Local copies of the Figma icon exports used by the account and state
/// screens (all `assets/images/*.svg`, 1.8 px navy strokes).
abstract final class KoloIcons {
  static const mailCheck = 'assets/images/b7f9364a64a0a7ceef2f.svg';
  static const mail = 'assets/images/9b29adadf19eaf18f946.svg';
  static const clockAlert = 'assets/images/a800d93bea91812d30e0.svg';
  static const keyRound = 'assets/images/52977f2de2817e3b55cb.svg';
  static const circleCheck = 'assets/images/5ee20178be752bf9479c.svg';
  static const shieldCheck = 'assets/images/255bbccb1cbb9e330a19.svg';
  static const shieldCheckPlain = 'assets/images/001c06421adf29482403.svg';
  static const userRoundCheck = 'assets/images/8e1f590415341fba43d7.svg';
  static const circleAlert = 'assets/images/11bdd18b376a0534d656.svg';
  static const info = 'assets/images/d8eedea853f449ea1543.svg';
  static const loader = 'assets/images/ca4c1bcc5542a3416b63.svg';
  static const emblem = 'assets/images/88dfdf7ffa8d70c62080.svg';
  static const chartNoAxes = 'assets/images/5b85dca48e7671a667a1.svg';
  static const cloudUpload = 'assets/images/b8b6f386e7fec243e8f7.svg';
  static const videoOff = 'assets/images/f523f033e54d4ea7bfa8.svg';
  static const shieldAlert = 'assets/images/a6231cbc39941a194e8d.svg';
  static const wifiOff = 'assets/images/f175639d9525b14b3858.svg';
  static const cloudOff = 'assets/images/cf55c6bf1c919f5c36b1.svg';
  static const searchX = 'assets/images/3688066412462a9cc404.svg';
  static const triangleAlert = 'assets/images/e8e8a03ba6dd35fbf97e.svg';
  static const lockKeyhole = 'assets/images/a31a69c3cef5c90d08b2.svg';
  static const shieldBan = 'assets/images/d4291633db8d1b507d90.svg';
  static const clipboardCheck = 'assets/images/fd18c882d12a2a9d4106.svg';
  static const badgeCheck = 'assets/images/ef06f9af14bb3097c9ec.svg';
  static const clock3 = 'assets/images/cf3ec46737707b4fdc9a.svg';
  static const rotateCcw = 'assets/images/e86250b3ab559a10656f.svg';
  static const userRoundX = 'assets/images/e2e09b68a17805674b06.svg';
  static const circleHelp = 'assets/images/66f784e9986a4b86faf3.svg';
}

/// Rounded soft-blue "State emblem" (80 pt, 24 pt radius) holding a Figma icon,
/// centred above the headline of the resend, expired and reset-complete
/// screens. With [plain] the icon is drawn alone, 48 pt, left-aligned (the
/// verify, key, user-check and shield variants).
class KoloMedallion extends StatelessWidget {
  const KoloMedallion(this.asset,
      {super.key, this.plain = false, Alignment? alignment})
      : alignment =
            alignment ?? (plain ? Alignment.centerLeft : Alignment.center);
  final String asset;
  final bool plain;
  final Alignment alignment;

  @override
  Widget build(BuildContext context) => Align(
        alignment: alignment,
        child: ExcludeSemantics(
          child: plain
              ? SvgPicture.asset(asset, width: 48, height: 48)
              : Container(
                  width: 80,
                  height: 80,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                      color: KoloVibeColors.softBlue,
                      borderRadius: BorderRadius.circular(24)),
                  child: SvgPicture.asset(asset, width: 36, height: 36)),
        ),
      );
}

/// Inline information, success or alert card with a Figma icon. Used where
/// the approved design shows a note that is not a plain [KoloNote] (for
/// example the white "Use the most recent code" card).
class KoloCard extends StatelessWidget {
  const KoloCard({super.key, required this.title, required this.message});
  final String title, message;

  @override
  Widget build(BuildContext context) => Semantics(
        container: true,
        child: Container(
          width: double.infinity,
          margin: const EdgeInsets.only(bottom: 16),
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(KoloVibeRadii.card)),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title,
                style: KoloVibeText.body(14,
                    weight: FontWeight.w600, color: KoloVibeColors.navy)),
            const SizedBox(height: 16),
            Text(message, style: KoloVibeText.body(13, height: 1.5)),
          ]),
        ),
      );
}

/// Large boxed entry for the emailed verification or reset code, drawn like the
/// approved six-digit boxes (white, 12 pt radius, navy 1.5 pt border, 24 pt
/// bold). The code issued by the identity service is a long URL-safe token, so
/// it is one masked field rather than six boxes; see the design decisions in
/// `docs/mobile-design-coverage.md`.
class KoloCodeField extends StatefulWidget {
  const KoloCodeField({
    super.key,
    required this.controller,
    this.semanticLabel = 'Verification code',
    this.hint = 'Paste the code from your email',
    this.onChanged,
    this.validator,
  });
  final TextEditingController controller;
  final String semanticLabel, hint;
  final ValueChanged<String>? onChanged;
  final FormFieldValidator<String>? validator;

  @override
  State<KoloCodeField> createState() => _KoloCodeFieldState();
}

class _KoloCodeFieldState extends State<KoloCodeField> {
  bool hidden = true;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: Semantics(
          label: widget.semanticLabel,
          textField: true,
          child: TextFormField(
            controller: widget.controller,
            obscureText: hidden,
            maxLength: 128,
            autocorrect: false,
            enableSuggestions: false,
            autofillHints: const [AutofillHints.oneTimeCode],
            onChanged: widget.onChanged,
            validator: widget.validator,
            textAlign: TextAlign.center,
            style: KoloVibeText.body(22,
                weight: FontWeight.w700, color: KoloVibeColors.navy),
            decoration: InputDecoration(
              hintText: widget.hint,
              hintStyle: KoloVibeText.body(14, color: KoloVibeColors.muted),
              counterText: '',
              fillColor: Colors.white,
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 20),
              border: _border(KoloVibeColors.navy),
              enabledBorder: _border(KoloVibeColors.navy),
              focusedBorder: _border(KoloVibeColors.navy, 2),
              errorBorder: _border(KoloVibeColors.red),
              focusedErrorBorder: _border(KoloVibeColors.red, 2),
              suffixIcon: IconButton(
                  tooltip: hidden ? 'Show code' : 'Hide code',
                  onPressed: () => setState(() => hidden = !hidden),
                  icon: Icon(
                      hidden
                          ? Icons.visibility_off_outlined
                          : Icons.visibility_outlined,
                      size: 20,
                      color: KoloVibeColors.muted)),
            ),
          ),
        ),
      );

  OutlineInputBorder _border(Color color, [double width = 1.5]) =>
      OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: color, width: width));
}
