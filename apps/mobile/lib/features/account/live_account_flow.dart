import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/presentation/feature_repository.dart';
import '../../core/theme/kolovibe_theme.dart';
import '../../shared/widgets/kolo_components.dart';
import '../system/system_ui.dart';
import 'live_account_repository.dart';

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

class LiveAccountFlowScreen extends StatefulWidget {
  const LiveAccountFlowScreen({
    super.key,
    required this.screen,
    required this.account,
    required this.catalog,
    this.initialEmail = '',
    this.setupAfterLogin = false,
    this.completed = false,
    this.message,
  });
  final int screen;
  final LiveAccountRepository account;
  final DesignCatalog catalog;
  final String initialEmail;
  final bool setupAfterLogin, completed;
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
  bool resendAcknowledged = false;
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
    if (protected) loadAccount();
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
    if (id == 5 && !agreed) {
      setState(() => fieldError = 'Acknowledge the terms before continuing.');
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
              'verificationCode': code.text,
              'Reset code': code.text,
              if (id == 82) 'Current password': current.text,
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
      }
      dirty = false;
    } on ApiFailure catch (failure) {
      if (id == 5 && failure.status == 409) {
        next = 12;
      } else if ({4, 15}.contains(id) && {400, 401}.contains(failure.status)) {
        next = 15;
        message =
            'Sign-in could not be completed. Check your details and try again.';
      } else if (id == 6 && failure.status == 400) {
        next = 8;
        message = 'The code was not accepted. It may have expired.';
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
        setupAfterLogin: operation == UiOperation.verifyEmail ? true : null,
        message: message,
      );
    } else if (error == null && fieldError == null && message != null) {
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
          if (verification && v.length < 32) {
            return 'Enter the full code from your email.';
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
  Widget footnote(String text) => Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Text(text,
            textAlign: TextAlign.center,
            style: KoloVibeText.body(11, height: 1.5)),
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

  List<Widget> content() => switch (id) {
        4 || 15 => [
            if (id == 4) wordmark,
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
                  icon: Icons.error_outline,
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
            footnote(id == 4
                ? 'Your account. Your community. Keep it secure.'
                : 'Still having trouble? Visit Help & Support.'),
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
            field('Confirm password', confirm,
                secret: true, match: true, hint: 'Repeat password'),
            CheckboxListTile(
              value: agreed,
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              onChanged: (v) => setState(() {
                agreed = v ?? false;
                dirty = true;
              }),
              title: Text('I acknowledge the Terms and Privacy information.',
                  style: KoloVibeText.body(12, height: 1.4)),
            ),
            const SizedBox(height: 8),
            button('Create account', UiOperation.register),
            link('Already registered? Sign in', 4),
            footnote('We’ll send a verification code to your email.'),
          ],
        6 => [
            headline('One small step.\nThen you’re in.'),
            lead(email.text.isEmpty
                ? 'Enter the full code sent to your email.'
                : 'Enter the code sent to ${email.text}. Keep this code private.'),
            field('Verification code', code,
                secret: true, verification: true, hint: 'Verification code'),
            button('Verify email', UiOperation.verifyEmail),
            link('Didn’t receive a code?', 7),
            link('Use a different email', 5),
          ],
        7 || 8 => [
            headline(id == 8 ? 'Let’s get a fresh code.' : 'Check your inbox.'),
            lead(id == 8
                ? 'Enter your email address to request a new verification code.'
                : 'Request a new verification code for an email you own.'),
            field('Email address', email,
                emailField: true, maximum: 254, hint: 'you@example.com'),
            if (resendAcknowledged)
              const KoloNote(
                  title: 'Use the most recent code',
                  message:
                      'If eligible, you will receive a new code. Use only the latest code and check spam folders.',
                  icon: Icons.mark_email_read_outlined,
                  tone: KoloNoteTone.success)
            else
              KoloNote(
                  title: id == 8
                      ? 'Your account is not verified yet'
                      : 'Use the most recent code',
                  message: 'Use only the latest code sent to your email.'),
            button('Request a new code', UiOperation.requestCode),
            link('Return to code entry', 6),
            link('Use a different email', 5),
          ],
        9 => [
            headline('Back to your vibe.'),
            lead(
                'Enter your account email and we’ll help you reset your password.'),
            field('Email address', email,
                emailField: true, maximum: 254, hint: 'you@example.com'),
            button('Send reset instructions', UiOperation.requestReset),
            link('Back to sign in', 4),
            footnote(
                'For your privacy, this message does not confirm whether an account exists.'),
          ],
        10 => [
            headline('A fresh start.\nA stronger password.'),
            lead('Choose a password you don’t use elsewhere.'),
            field('Reset code', code,
                secret: true, verification: true, hint: 'Code from your email'),
            field('New password', password, secret: true, hint: 'New password'),
            field('Confirm password', confirm,
                secret: true, match: true, hint: 'Repeat password'),
            const KoloNote(
                title: 'Current password requirements',
                message:
                    'Use the requirements supplied by the account service.'),
            button('Reset password', UiOperation.resetPassword),
            link('Back to sign in', 4),
          ],
        11 => [
            wordmark,
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
                  icon: Icons.check_circle_outline,
                  tone: KoloNoteTone.success),
            FilledButton(
                onPressed: busy ? null : () => leave(4),
                child: const Text('Return to sign in')),
          ],
        12 => [
            headline('You may already\nbe part of the vibe.'),
            lead(
                'This email can’t be used for a new registration. Try signing in or recovering your account.'),
            if (email.text.isNotEmpty)
              field('Email address', email, readOnly: true, maximum: 254),
            link('Sign in instead', 4),
            link('Reset my password', 9),
            link('Use another email', 5),
            const KoloNote(
                title: 'Keep your account safe',
                message: 'Only continue with an email you own.'),
          ],
        13 || 80 => [
            if (id == 13)
              headline('What should\nwe call you?')
            else
              headline('Edit personal profile'),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text(
                      'Profile photos are not available yet. Photo moderation policy is pending.',
                    ),
                  ),
                ),
                child: Text('Add or change photo · Optional',
                    style: KoloVibeText.body(13,
                        weight: FontWeight.w600, color: KoloVibeColors.red)),
              ),
            ),
            field('Display name', name,
                maximum: 80,
                hint: 'Your name',
                helper: 'This is how your name appears in the community.'),
            field('Account email', email, readOnly: true, maximum: 254),
            if (id == 13)
              lead(
                  'Start as a viewer. You can explore creator onboarding whenever you’re ready.'),
            button(
              id == 13 ? 'Continue to KoloVibe' : 'Save changes',
              UiOperation.saveProfile,
            ),
            if (id == 13)
              OutlinedButton(
                  onPressed:
                      busy ? null : () => submit(UiOperation.saveProfile),
                  child: const Text('Skip photo for now'))
            else
              link('Cancel', 79),
          ],
        16 => [
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
                icon: Icons.lock_outline),
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
                            if (widget.message != null)
                              KoloNote(
                                  title: 'Notice', message: widget.message!),
                            if (busy)
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
