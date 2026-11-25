import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/presentation/feature_repository.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../system/system_ui.dart';
import '../creators/creator_shell.dart';
import 'live_account_repository.dart';
import '../legal/legal_screens.dart';
import '../legal/live_legal_repository.dart';

const accountFormScreens = {4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 80, 82};

/// Typed, in-memory return to the sensitive caller. The proof is not put in
/// ScreenRoute, AppSession, a URL, restoration state or persistent storage.
Future<Reauthentication?> confirmIdentity(
  BuildContext context,
  LiveAccountRepository account,
  DesignCatalog catalog,
) =>
    Navigator.of(context).push<Reauthentication>(
      MaterialPageRoute<Reauthentication>(
        settings: const RouteSettings(name: '/mobile/M-016'),
        builder: (_) => LiveAccountFlowScreen(
            screen: 16, account: account, catalog: catalog),
      ),
    );

final _sixDigits = RegExp(r'^[0-9]{6}$');

class LiveAccountFlowScreen extends StatefulWidget {
  const LiveAccountFlowScreen({
    super.key,
    required this.screen,
    required this.account,
    required this.catalog,
    this.initialEmail = '',
    this.setupAfterLogin = false,
    this.completed = false,
    this.unavailable = false,
    this.message,
  });
  final int screen;
  final LiveAccountRepository account;
  final DesignCatalog catalog;
  final String initialEmail;
  final bool setupAfterLogin, completed, unavailable;
  final String? message;
  @override
  State<LiveAccountFlowScreen> createState() => _LiveAccountFlowScreenState();
}

class _LiveAccountFlowScreenState extends State<LiveAccountFlowScreen> {
  final form = GlobalKey<FormState>();
  final email = TextEditingController(), name = TextEditingController();
  final password = TextEditingController(), confirm = TextEditingController();
  final current = TextEditingController(), code = TextEditingController();
  bool busy = false, loading = false, dirty = false, agreed = false;
  bool marketing = false;
  LegalSummary? termsText, privacyText, marketingText;
  Object? legalError;
  bool resendAcknowledged = false, resendUnavailable = false;
  bool resetRequested = false;
  int rejectedCodes = 0;
  Object? error;
  String? fieldError;
  LiveAccount? user;
  int get id => widget.screen;
  bool get protected => {13, 16, 80, 82}.contains(id);

  @override
  void initState() {
    super.initState();
    email.text = widget.initialEmail;
    resendAcknowledged = widget.completed;
    resendUnavailable = widget.unavailable;
    if (protected) loadAccount();
    if (id == 5) loadLegal();
  }

  LiveLegalRepository get legal => LiveLegalRepository(widget.account);

  /// Decision B: the current versions are fetched before the person can accept them.
  Future<void> loadLegal() async {
    setState(() => legalError = null);
    try {
      final docs = await Future.wait(legalKinds.map(legal.document));
      if (mounted) {
        setState(() {
          termsText = docs[0].summary;
          privacyText = docs[1].summary;
          marketingText = docs[2].summary;
        });
      }
    } catch (failure) {
      if (mounted) setState(() => legalError = failure);
    }
  }

  @override
  void dispose() {
    for (final value in [email, name, password, confirm, current, code]) {
      value.clear();
      value.dispose();
    }
    super.dispose();
  }

  Future<void> loadAccount() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final value = await widget.account.currentAccount();
      if (value == null) throw const ApiFailure(401, 'Sign in again.');
      if (mounted) {
        setState(() {
          user = value;
          email.text = value.email;
          name.text = value.displayName;
        });
      }
    } catch (failure) {
      if (mounted) setState(() => error = failure);
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void go(
    int target, {
    bool reset = false,
    bool completed = false,
    bool unavailable = false,
    bool? setupAfterLogin,
    String? message,
  }) {
    final route = ScreenRoute(target);
    if (accountFormScreens.contains(target) && !reset) {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          settings: RouteSettings(name: route.name, arguments: route),
          builder: (_) => LiveAccountFlowScreen(
            screen: target,
            account: widget.account,
            catalog: widget.catalog,
            initialEmail: email.text.trim(),
            setupAfterLogin: setupAfterLogin ?? widget.setupAfterLogin,
            completed: completed,
            unavailable: unavailable,
            message: message,
          ),
        ),
      );
    } else if (reset) {
      Navigator.of(context)
          .pushNamedAndRemoveUntil(route.name, (_) => false, arguments: route);
    } else {
      Navigator.of(context).pushReplacementNamed(route.name, arguments: route);
    }
  }

  Future<void> leave(int target) async {
    if (busy) return;
    if (dirty && !await confirmDiscard(context)) return;
    if (!mounted) return;
    setState(() => dirty = false);
    go(target);
  }

  Future<void> submit(UiOperation operation) async {
    if (busy || !(form.currentState?.validate() ?? false)) return;
    if (id == 5 && (termsText == null || privacyText == null)) {
      setState(() => fieldError =
          'The terms could not be loaded. Check your connection and try again.');
      return;
    }
    if (id == 5 && !agreed) {
      setState(() => fieldError =
          'Accept the Terms of Service and the Privacy Notice to continue.');
      return;
    }
    FocusScope.of(context).unfocus();
    setState(() {
      busy = true;
      fieldError = null;
      error = null;
    });
    int? next;
    String? message;
    Reauthentication? proof;
    try {
      if (id == 16) {
        proof = await widget.account.reauthenticate(current.text);
      } else {
        final result = await widget.account.executeChecked(
          UiRequest(
            operation,
            fields: {
              'Email address': email.text.trim(),
              'Full name': name.text.trim(),
              'Display name': name.text.trim(),
              'Password': password.text,
              'New password': password.text,
              'verificationCode': code.text.trim(),
              'Reset code': code.text.trim(),
              if (id == 82) 'Current password': current.text,
              if (id == 5) ...{
                'acceptedTerms': termsText!.version,
                'acceptedPrivacy': privacyText!.version,
                'marketingConsent': marketing ? 'true' : 'false',
              },
            },
          ),
        );
        if (!result.available) throw StateError(result.message);
        message = result.message;
        next = switch (operation) {
          UiOperation.signIn => widget.setupAfterLogin ? 13 : 79,
          UiOperation.register => 6,
          UiOperation.verifyEmail => 4,
          UiOperation.requestReset => 10,
          UiOperation.resetPassword => id == 82 ? null : 11,
          UiOperation.saveProfile => id == 13 ? 17 : 79,
          UiOperation.requestCode => id == 7 ? null : 7,
          _ => null,
        };
        if (operation == UiOperation.requestCode) resendAcknowledged = true;
        if (operation == UiOperation.requestCode) resendUnavailable = false;
        if (operation == UiOperation.requestReset) {
          resetRequested = true;
          next = null;
        }
      }
      dirty = false;
    } on ApiFailure catch (failure) {
      if (id == 5 && isOutdatedLegalVersion(failure)) {
        // A newer version was published while the form was open: show it and ask again.
        agreed = false;
        fieldError =
            'The terms were just updated. Read the new version, then accept it to continue.';
        loadLegal();
      } else if (id == 5 && failure.status == 409) {
        // Only a server from before ADR-013 A-2 answers 409 here; kept for the rollout window.
        next = 12;
      } else if ({4, 15}.contains(id) && {400, 401}.contains(failure.status)) {
        next = 15;
        message =
            'Sign-in could not be completed. Check your details and try again.';
      } else if (id == 6 && failure.status == 400) {
        // The service answers the same for a wrong, expired or used code, and destroys a code
        // after five wrong guesses, so after several misses a fresh code is the honest next step.
        rejectedCodes++;
        if (rejectedCodes >= 4) {
          next = 8;
          message =
              'That code can no longer be used. Request a new one to continue.';
        } else {
          fieldError =
              'That code didn’t work. Check the digits, or request a new code.';
        }
      } else if (id == 10 && failure.status == 400) {
        rejectedCodes++;
        fieldError = rejectedCodes >= 4
            ? 'That code can no longer be used. Go back and request a new one.'
            : failure.message;
      } else if (operation == UiOperation.requestCode &&
          failure.status == 429) {
        resendUnavailable = true;
        if (id == 8) next = 7;
      } else if ({400, 409}.contains(failure.status) ||
          !protected && failure.status == 401) {
        fieldError = failure.message;
      } else {
        error = failure;
      }
    } catch (failure) {
      error = failure;
    } finally {
      if (mounted) {
        for (final secret in [password, confirm, current, code]) {
          secret.clear();
        }
        setState(() => busy = false);
      } else {
        proof?.dispose();
      }
    }
    if (!mounted) return;
    if (proof != null) {
      if (Navigator.of(context).canPop()) {
        Navigator.of(context).pop(proof);
      } else {
        proof.dispose();
        go(79, reset: true);
      }
      return;
    }
    if (next != null) {
      if (next == 79 || next == 17) {
        go(next, reset: true);
        return;
      }
      go(
        next,
        completed: {7, 11}.contains(next),
        unavailable: resendUnavailable && next == 7,
        setupAfterLogin: operation == UiOperation.verifyEmail ? true : null,
        message: message,
      );
    } else if (error == null &&
        fieldError == null &&
        message != null &&
        operation != UiOperation.requestReset &&
        !(operation == UiOperation.requestCode && id == 7)) {
      notifySuccess(context, message);
      if (id == 82) {
        await showDialog<void>(
          context: context,
          builder: (dialog) => AlertDialog(
            title: const Text('Password updated'),
            content: const Text(
              'Other sessions have been signed out. Your current session remains active.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(dialog),
                child: const Text('Done'),
              ),
              TextButton(
                onPressed: () {
                  Navigator.pop(dialog);
                  go(83);
                },
                child: const Text('Review sessions'),
              ),
            ],
          ),
        );
      }
    }
  }

  Widget field(
    String label,
    TextEditingController value, {
    bool secret = false,
    bool readOnly = false,
    bool emailField = false,
    bool match = false,
    bool verification = false,
    int maximum = 128,
    String? hint,
    String? helper,
  }) =>
      KoloTextField(
        key: ValueKey(label),
        label: label,
        controller: value,
        hint: hint,
        helper: helper,
        secret: secret,
        readOnly: readOnly,
        maxLength: maximum,
        keyboardType:
            emailField ? TextInputType.emailAddress : TextInputType.text,
        autofillHints: readOnly
            ? null
            : emailField
                ? const [AutofillHints.email]
                : verification
                    ? const [AutofillHints.oneTimeCode]
                    : null,
        onChanged: readOnly ? null : (_) => setState(() => dirty = true),
        validator: (text) {
          if (readOnly) return null;
          final v = text ?? '';
          if (v.isEmpty) return 'Enter $label.';
          if (emailField &&
              !RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(v.trim())) {
            return 'Enter a valid email address.';
          }
          if (match && v != password.text) {
            return 'The passwords don’t match.';
          }
          if (verification && !_sixDigits.hasMatch(v)) {
            return 'Enter the six-digit code from your email.';
          }
          if (label == 'Display name' && v.trim().length < 2 ||
              label == 'Full name' && v.trim().length < 2) {
            return 'Enter at least two characters.';
          }
          return null;
        },
      );

  /// Primary (red) action. A rejected submission is explained directly above
  /// it, where the person is looking, rather than at the top of the page.
  Widget button(String label, UiOperation operation) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (fieldError != null)
            Semantics(
              liveRegion: true,
              child: Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(fieldError!,
                    style: KoloVibeText.body(12, color: KoloVibeColors.red)),
              ),
            ),
          FilledButton(
            onPressed: busy ? null : () => submit(operation),
            child: Text(label),
          ),
        ]),
      );

  /// Secondary (soft blue) navigation action.
  Widget link(String label, int target) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: OutlinedButton(
          onPressed: busy ? null : () => leave(target),
          child: Text(label),
        ),
      );

  Widget headline(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: KoloHeadline(text),
      );
  Widget lead(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 20),
        child: Text(text, style: KoloVibeText.body(14, height: 1.5)),
      );
  Widget footnote(String text, {TextAlign align = TextAlign.center}) => Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Text(text,
            textAlign: align, style: KoloVibeText.body(11, height: 1.5)),
      );
  Widget textLink(String label, int target) => Align(
        alignment: Alignment.centerLeft,
        child: TextButton(
          onPressed: busy ? null : () => leave(target),
          style: TextButton.styleFrom(
              foregroundColor: KoloVibeColors.red,
              padding: EdgeInsets.zero,
              minimumSize: const Size(44, 44)),
          child: Text(label),
        ),
      );
  Widget get wordmark => const Padding(
        padding: EdgeInsets.only(bottom: 20),
        child: Align(alignment: Alignment.centerLeft, child: KoloWordmark()),
      );

  /// Soft secondary action drawn as plain bold text (the approved "Back to
  /// sign in" and "Use another email" rows).
  Widget plainLink(String label, int target) => Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: TextButton(
          style: TextButton.styleFrom(
              minimumSize: const Size.fromHeight(50),
              textStyle: KoloVibeText.body(14, weight: FontWeight.w700)),
          onPressed: busy ? null : () => leave(target),
          child: Text(label),
        ),
      );

  Widget get busyButton => Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: Container(
          constraints: const BoxConstraints(minHeight: 50),
          decoration: BoxDecoration(
              color: const Color(0xFFDCE5F7),
              borderRadius: BorderRadius.circular(12)),
          alignment: Alignment.center,
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                    strokeWidth: 2, color: KoloVibeColors.navy)),
            const SizedBox(width: 8),
            Text('Verifying…',
                style: KoloVibeText.body(14,
                    weight: FontWeight.w700, color: KoloVibeColors.muted)),
          ]),
        ),
      );

  List<Widget> content() => switch (id) {
        4 || 15 => [
            if (id == 4 || id == 15) wordmark,
            headline(id == 15
                ? 'We couldn’t\nsign you in.'
                : 'Welcome back.\nYour vibe awaits.'),
            if (id == 4)
              lead(
                  'Sign in to follow your favourites and discover more original stories.')
            else
              const KoloNote(
                  title: 'Authentication couldn’t be completed',
                  message:
                      'Your connection or sign-in service may have interrupted the request. Your password is not shown.',
                  asset: KoloIcons.circleAlert,
                  tone: KoloNoteTone.alert),
            field('Email address', email,
                emailField: true, maximum: 254, hint: 'you@example.com'),
            field('Password', password,
                secret: true,
                hint: id == 15 ? 'Enter your password again' : 'Password'),
            if (id == 4) textLink('Forgot password?', 9),
            button(id == 15 ? 'Try signing in again' : 'Sign in',
                UiOperation.signIn),
            if (id == 4)
              link('New here? Create an account', 5)
            else
              link('Recover my account', 9),
            footnote(
                id == 4
                    ? 'Your account. Your community. Keep it secure.'
                    : 'Still having trouble? Visit Help & Support.',
                align: id == 4 ? TextAlign.center : TextAlign.start),
          ],
        5 => [
            headline('Your next favourite\nstory starts here.'),
            const SizedBox(height: 8),
            field('Full name', name, maximum: 80, hint: 'Your name'),
            field('Email address', email,
                emailField: true, maximum: 254, hint: 'you@example.com'),
            field('Password', password,
                secret: true,
                hint: 'Password',
                helper:
                    'Use a unique password. Requirements are checked by the account service.'),
            if (legalError != null)
              TextButton(
                  key: const ValueKey('legal-retry'),
                  onPressed: loadLegal,
                  child: const Text('The terms could not be loaded. Try again.'))
            else if (termsText != null && privacyText != null) ...[
              if (termsText!.pendingLegalReview || privacyText!.pendingLegalReview)
                const LegalReviewNote(),
              Wrap(
                spacing: 4,
                children: [
                  TextButton(
                      key: const ValueKey('read-terms'),
                      onPressed: () => openLegalDocument(context, legal, 'terms'),
                      child: const Text('Read the Terms of Service')),
                  TextButton(
                      key: const ValueKey('read-privacy'),
                      onPressed: () => openLegalDocument(context, legal, 'privacy'),
                      child: const Text('Read the Privacy Notice')),
                ],
              ),
            ],
            CheckboxListTile(
              key: const ValueKey('accept-legal'),
              value: agreed,
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              onChanged: termsText == null
                  ? null
                  : (v) => setState(() {
                        agreed = v ?? false;
                        dirty = true;
                      }),
              title: Text(
                  'I accept the Terms of Service (version ${termsText?.version ?? '…'}) and the Privacy Notice (version ${privacyText?.version ?? '…'}).',
                  style: KoloVibeText.body(12, height: 1.4)),
            ),
            CheckboxListTile(
              key: const ValueKey('marketing-consent'),
              value: marketing,
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              onChanged: marketingText == null
                  ? null
                  : (v) => setState(() {
                        marketing = v ?? false;
                        dirty = true;
                      }),
              title: Text(
                  'Optional: send me news about new features and offers. I can turn this off at any time.',
                  style: KoloVibeText.body(12, height: 1.4)),
            ),
            const SizedBox(height: 8),
            button('Create account', UiOperation.register),
            link('Already registered? Sign in', 4),
            footnote('We’ll send a verification code to your email.'),
          ],
        6 => [
            const KoloMedallion(KoloIcons.mailCheck, plain: true),
            const SizedBox(height: 16),
            headline('One small step.\nThen you’re in.'),
            lead(email.text.isEmpty
                ? 'Enter the full code sent to your email.'
                : 'Enter the code sent to ${email.text}. Keep this code private.'),
            if (email.text.isEmpty)
              field('Email address', email,
                  emailField: true, maximum: 254, hint: 'you@example.com'),
            KoloCodeField(
              key: const ValueKey('Verification code'),
              controller: code,
              enabled: !busy,
              onChanged: (_) => setState(() => dirty = true),
              validator: (text) => _sixDigits.hasMatch(text ?? '')
                  ? null
                  : 'Enter the six-digit code from your email.',
            ),
            if (busy)
              busyButton
            else
              button('Verify email', UiOperation.verifyEmail),
            if (busy)
              const KoloNote(
                  title: 'Checking your code',
                  message:
                      'Please keep this screen open while we confirm your email.'),
            Center(
              child: TextButton(
                onPressed: busy ? null : () => leave(7),
                style: TextButton.styleFrom(
                    minimumSize: const Size(44, 50),
                    textStyle: KoloVibeText.body(14, weight: FontWeight.w700)),
                child: const Text('Didn’t receive a code?'),
              ),
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: busy ? null : () => leave(5),
                style: TextButton.styleFrom(
                    foregroundColor: KoloVibeColors.muted,
                    padding: EdgeInsets.zero,
                    minimumSize: const Size(44, 44),
                    textStyle: KoloVibeText.body(12)),
                child: const Text('Wrong email? Return to registration.'),
              ),
            ),
            // Registration answers the same for a new and an existing address (ADR-013 A-2), so M-012 is
            // offered here instead of after a 409.
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: busy ? null : () => leave(12),
                style: TextButton.styleFrom(
                    foregroundColor: KoloVibeColors.muted,
                    padding: EdgeInsets.zero,
                    minimumSize: const Size(44, 44),
                    textStyle: KoloVibeText.body(12)),
                child: const Text('Already have an account?'),
              ),
            ),
          ],
        7 when resendAcknowledged || resendUnavailable => [
            const KoloMedallion(KoloIcons.mail),
            const SizedBox(height: 24),
            headline('Check your inbox'),
            lead(email.text.isEmpty
                ? 'A new verification code was requested.'
                : 'A new verification code was requested for ${email.text}.'),
            const KoloCard(
                title: 'Use the most recent code',
                message:
                    'If eligible, you will receive a new code. Check spam or junk folders too. Never share your code with anyone.'),
            if (resendUnavailable) ...[
              const KoloNote(
                  title: 'Another request isn’t available yet',
                  message:
                      'Follow the retry guidance shown by the verification service. No need to request repeatedly.'),
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: OutlinedButton(
                    onPressed: null,
                    style: OutlinedButton.styleFrom(
                        disabledBackgroundColor: const Color(0xFFDCE5F7)),
                    child: const Text('Resend unavailable')),
              ),
            ],
            link('Return to code entry', 6),
            plainLink('Use a different email', 5),
          ],
        7 || 8 => [
            if (id == 8) const KoloMedallion(KoloIcons.clockAlert),
            if (id == 7) const KoloMedallion(KoloIcons.mail),
            const SizedBox(height: 24),
            headline(id == 8 ? 'Let’s get a fresh code' : 'Check your inbox'),
            lead(id == 8
                ? 'This verification code has expired. Request a new code to continue safely.'
                : 'Request a new verification code for an email you own.'),
            field('Email address', email,
                emailField: true, maximum: 254, hint: 'you@example.com'),
            KoloNote(
                title: id == 8
                    ? 'Your account is not verified yet'
                    : 'Use the most recent code',
                message: 'Use only the latest code sent to your email.',
                asset: KoloIcons.info),
            button('Request a new code', UiOperation.requestCode),
            if (id == 8)
              link('Back to sign in', 4)
            else
              link('Return to code entry', 6),
            if (id == 7) plainLink('Use a different email', 5),
          ],
        9 => [
            const KoloMedallion(KoloIcons.keyRound, plain: true),
            const SizedBox(height: 16),
            headline('Back to your vibe.'),
            lead(
                'Enter your account email and we’ll help you reset your password.'),
            field('Email address', email,
                emailField: true, maximum: 254, hint: 'you@example.com'),
            if (resetRequested)
              const KoloNote(
                  title: 'Check your email',
                  message:
                      'If an account matches this email, you’ll receive password reset instructions.',
                  asset: KoloIcons.circleCheck,
                  tone: KoloNoteTone.success),
            button('Send reset instructions', UiOperation.requestReset),
            if (resetRequested) link('Enter reset code', 10),
            link('Return to sign in', 4),
            footnote(
                'For your privacy, this message does not confirm whether an account exists.',
                align: TextAlign.start),
          ],
        10 => [
            headline('A fresh start.\nA stronger password.'),
            lead('Choose a password you don’t use elsewhere.'),
            if (email.text.isEmpty)
              field('Email address', email,
                  emailField: true, maximum: 254, hint: 'you@example.com'),
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text('Code from your email',
                  style: KoloVibeText.body(12,
                      weight: FontWeight.w600, color: KoloVibeColors.navy)),
            ),
            KoloCodeField(
              key: const ValueKey('Reset code'),
              controller: code,
              semanticLabel: 'Reset code',
              enabled: !busy,
              onChanged: (_) => setState(() => dirty = true),
              validator: (text) => _sixDigits.hasMatch(text ?? '')
                  ? null
                  : 'Enter the six-digit code from your email.',
            ),
            field('New password', password, secret: true, hint: 'New password'),
            field('Confirm password', confirm,
                secret: true, match: true, hint: 'Repeat password'),
            const KoloNote(
                title: 'Current password requirements',
                message:
                    'Use the requirements supplied by the account service. Your password is checked when you save.',
                asset: KoloIcons.info),
            button('Reset password', UiOperation.resetPassword),
            plainLink('Back to sign in', 4),
          ],
        11 => [
            wordmark,
            const KoloMedallion(KoloIcons.shieldCheck),
            const SizedBox(height: 20),
            headline(widget.completed
                ? 'You’re secure.\nLet’s get you back.'
                : 'Password not changed.'),
            lead(widget.completed
                ? 'Your new password has been saved. Use it the next time you sign in.'
                : 'No password reset has been confirmed in this flow.'),
            if (widget.completed)
              const KoloNote(
                  title: 'Password updated',
                  message:
                      'Keep your sign-in details private and use a unique password.',
                  asset: KoloIcons.circleCheck,
                  tone: KoloNoteTone.success),
            FilledButton(
                onPressed: busy ? null : () => leave(4),
                child: const Text('Return to sign in')),
          ],
        12 => [
            const KoloMedallion(KoloIcons.userRoundCheck, plain: true),
            const SizedBox(height: 16),
            headline('You may already\nbe part of the vibe.'),
            lead(
                'This email can’t be used for a new registration. Try signing in or recovering your account.'),
            field('Email address', email,
                readOnly: email.text.isNotEmpty,
                emailField: true,
                maximum: 254,
                hint: 'you@example.com'),
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: FilledButton(
                  onPressed: busy ? null : () => leave(4),
                  child: const Text('Sign in instead')),
            ),
            link('Reset my password', 9),
            plainLink('Use another email', 5),
            const SizedBox(height: 12),
            const KoloNote(
                title: 'Keep your account safe',
                message: 'Only continue with an email you own.',
                asset: KoloIcons.info),
          ],
        13 || 80 => [
            if (id == 13)
              headline('What should\nwe call you?')
            else
              headline('Edit personal profile'),
            const SizedBox(height: 8),
            Row(children: [
              KoloAvatar(name: name.text, size: 64),
              const SizedBox(width: 12),
              Expanded(
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton(
                    onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text(
                          'Profile photos are not available yet. Photo moderation policy is pending.',
                        ),
                      ),
                    ),
                    child: Text(
                        id == 13 ? 'Add a photo · Optional' : 'Change photo',
                        style: KoloVibeText.body(13,
                            weight: FontWeight.w600,
                            color: KoloVibeColors.red)),
                  ),
                ),
              ),
            ]),
            const SizedBox(height: 12),
            field('Display name', name,
                maximum: 80,
                hint: 'Your name',
                helper: 'This is how your name appears in the community.'),
            field('Account email', email, readOnly: true, maximum: 254),
            if (id == 13)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Wrap(spacing: 8, runSpacing: 8, children: [
                  KoloBadge('Name added', filled: name.text.trim().length >= 2),
                  const KoloBadge('Photo optional'),
                ]),
              ),
            if (id == 13)
              lead(
                  'Start as a viewer. You can explore creator onboarding whenever you’re ready.'),
            button(
              id == 13 ? 'Continue to KoloVibe' : 'Save changes',
              UiOperation.saveProfile,
            ),
            if (id == 13)
              TextButton(
                  style: TextButton.styleFrom(
                      minimumSize: const Size.fromHeight(50),
                      textStyle:
                          KoloVibeText.body(14, weight: FontWeight.w700)),
                  onPressed:
                      busy ? null : () => submit(UiOperation.saveProfile),
                  child: const Text('Skip photo for now'))
            else
              link('Cancel', 79),
          ],
        16 => [
            const KoloMedallion(KoloIcons.shieldCheckPlain, plain: true),
            const SizedBox(height: 16),
            headline('A little extra\nprotection.'),
            lead(
                'Verify your identity before continuing. Nothing is deleted at this step.'),
            field('Account email', email, readOnly: true, maximum: 254),
            field('Current password', current,
                secret: true, hint: 'Enter current password'),
            const KoloNote(
                title: 'Secure return',
                message:
                    'After verification, you’ll return to the deletion confirmation. Nothing is deleted at this step.',
                asset: KoloIcons.info),
            button('Verify identity', UiOperation.reauthenticate),
            OutlinedButton(
              onPressed: busy ? null : () => Navigator.maybePop(context),
              child: const Text('Cancel and return to account'),
            ),
          ],
        82 => [
            field('Current password', current,
                secret: true, hint: 'Current password'),
            field('New password', password, secret: true, hint: 'New password'),
            field('Confirm password', confirm,
                secret: true, match: true, hint: 'Repeat password'),
            button('Change password', UiOperation.resetPassword),
            link('Back to security', 85),
          ],
        _ => [],
      };

  @override
  Widget build(BuildContext context) => UnsavedChangesGuard(
        dirty: dirty,
        busy: busy,
        onDiscardRoot: () => go(protected ? 79 : 2, reset: true),
        child: Scaffold(
          key: ValueKey('live-M-${id.toString().padLeft(3, '0')}'),
          // Profile-area forms carry the designed primary navigation.
          bottomNavigationBar: {80, 82}.contains(id)
              ? creatorNavigation(context, widget.catalog, id)
              : null,
          appBar: AppBar(
            title: Text(widget.catalog[id].name),
            leading: IconButton(
              tooltip: 'Back',
              icon: const Icon(Icons.arrow_back),
              onPressed: busy
                  ? null
                  : () {
                      if (Navigator.of(context).canPop()) {
                        Navigator.maybePop(context);
                      } else {
                        leave(protected ? 79 : 2);
                      }
                    },
            ),
          ),
          body: SafeArea(
            child: loading
                ? const SystemLoading()
                : error != null
                    ? SystemFailureView(
                        error: error!,
                        onRetry: () {
                          if (protected && user == null) {
                            loadAccount();
                          } else {
                            setState(() => error = null);
                          }
                        },
                        onSignIn: () => go(4, reset: true),
                      )
                    : Form(
                        key: form,
                        child: ListView(
                          padding: const EdgeInsets.fromLTRB(24, 8, 24, 32),
                          keyboardDismissBehavior:
                              ScrollViewKeyboardDismissBehavior.onDrag,
                          children: [
                            if (widget.message != null && !widget.completed)
                              KoloNote(
                                  title: 'Notice', message: widget.message!),
                            if (busy && id != 6)
                              const Padding(
                                  padding: EdgeInsets.only(bottom: 12),
                                  child: LinearProgressIndicator()),
                            ...content(),
                          ],
                        ),
                      ),
          ),
        ),
      );
}
