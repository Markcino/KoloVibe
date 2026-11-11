import 'package:flutter/material.dart';

import '../../app/screen_route.dart';
import '../../core/network/api_client.dart';
import '../../core/presentation/design_node.dart';
import '../../core/presentation/feature_repository.dart';
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
  }) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: TextFormField(
          key: ValueKey(label),
          controller: value,
          readOnly: readOnly,
          obscureText: secret,
          maxLength: maximum,
          autocorrect: !secret,
          enableSuggestions: !secret,
          keyboardType:
              emailField ? TextInputType.emailAddress : TextInputType.text,
          autofillHints: readOnly
              ? null
              : emailField
                  ? const [AutofillHints.email]
                  : verification
                      ? const [AutofillHints.oneTimeCode]
                      : null,
          decoration: InputDecoration(labelText: label, counterText: ''),
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
        ),
      );

  Widget button(String label, UiOperation operation) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: FilledButton(
          onPressed: busy ? null : () => submit(operation),
          child: Text(label),
        ),
      );
  Widget link(String label, int target) => TextButton(
        onPressed: busy ? null : () => leave(target),
        child: Text(label),
      );

  List<Widget> content() => switch (id) {
        4 || 15 => [
            Text(
              id == 15 ? 'We couldn’t sign you in.' : 'Welcome back.',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            field('Email address', email, emailField: true, maximum: 254),
            field('Password', password, secret: true),
            button(id == 15 ? 'Try signing in again' : 'Sign in',
                UiOperation.signIn),
            link('Forgot password?', 9),
            link('Create an account', 5),
          ],
        5 => [
            const Text('Join the vibe.'),
            field('Full name', name, maximum: 80),
            field('Email address', email, emailField: true, maximum: 254),
            field('Password', password, secret: true),
            field('Confirm password', confirm, secret: true, match: true),
            const Text(
              'Use a unique password. Requirements are checked by the account service.',
            ),
            CheckboxListTile(
              value: agreed,
              onChanged: (v) => setState(() {
                agreed = v ?? false;
                dirty = true;
              }),
              title: const Text(
                  'I acknowledge the Terms and Privacy information.'),
            ),
            button('Create account', UiOperation.register),
            link('Already have an account? Sign in', 4),
          ],
        6 => [
            const Text('One small step. Then you’re in.'),
            Text(
              email.text.isEmpty
                  ? 'Enter the full code sent to your email.'
                  : 'Enter the code sent to ${email.text}. Keep this code private.',
            ),
            field('Verification code', code, secret: true, verification: true),
            button('Verify email', UiOperation.verifyEmail),
            link('Didn’t receive a code?', 7),
            link('Use a different email', 5),
          ],
        7 || 8 => [
            Text(id == 8 ? 'Let’s get a fresh code.' : 'Check your inbox.'),
            field('Email address', email, emailField: true, maximum: 254),
            Text(
              resendAcknowledged
                  ? 'If eligible, you will receive a new code. Use only the latest code and check spam folders.'
                  : 'Request a new verification code for an email you own.',
            ),
            button('Request a new code', UiOperation.requestCode),
            link('Return to code entry', 6),
            link('Use a different email', 5),
          ],
        9 => [
            const Text('Let’s get you back.'),
            field('Email address', email, emailField: true, maximum: 254),
            button('Send reset instructions', UiOperation.requestReset),
            link('Back to sign in', 4),
          ],
        10 => [
            const Text('A fresh start. A stronger password.'),
            field('Reset code', code, secret: true, verification: true),
            field('New password', password, secret: true),
            field('Confirm password', confirm, secret: true, match: true),
            const Text('Use the requirements supplied by the account service.'),
            button('Reset password', UiOperation.resetPassword),
            link('Back to sign in', 4),
          ],
        11 => [
            Text(
              widget.completed
                  ? 'Your new password has been saved. Use it the next time you sign in.'
                  : 'No password reset has been confirmed in this flow.',
            ),
            link('Return to sign in', 4),
          ],
        12 => [
            const Text(
              'This email can’t be used for a new registration. Try signing in or recovering your account.',
            ),
            if (email.text.isNotEmpty) Text(email.text),
            link('Sign in instead', 4),
            link('Reset my password', 9),
            link('Use another email', 5),
          ],
        13 || 80 => [
            Text(id == 13
                ? 'What should we call you?'
                : 'Edit personal profile'),
            TextButton(
              onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text(
                    'Profile photos are not available yet. Photo moderation policy is pending.',
                  ),
                ),
              ),
              child: const Text('Add or change photo · Optional'),
            ),
            field('Display name', name, maximum: 80),
            field('Account email', email, readOnly: true, maximum: 254),
            button(
              id == 13 ? 'Continue to KoloVibe' : 'Save changes',
              UiOperation.saveProfile,
            ),
            if (id == 13)
              button('Skip photo for now', UiOperation.saveProfile)
            else
              link('Cancel', 79),
          ],
        16 => [
            const Text('A little extra protection.'),
            const Text(
              'Verify your identity before continuing. Nothing is deleted at this step.',
            ),
            field('Account email', email, readOnly: true, maximum: 254),
            field('Current password', current, secret: true),
            button('Verify identity', UiOperation.reauthenticate),
            TextButton(
              onPressed: busy ? null : () => Navigator.maybePop(context),
              child: const Text('Cancel and return to account'),
            ),
          ],
        82 => [
            field('Current password', current, secret: true),
            field('New password', password, secret: true),
            field('Confirm password', confirm, secret: true, match: true),
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
                          padding: const EdgeInsets.all(24),
                          children: [
                            if (widget.message != null) Text(widget.message!),
                            if (fieldError != null)
                              Semantics(
                                  liveRegion: true, child: Text(fieldError!)),
                            if (busy) const SystemLoading(),
                            ...content(),
                          ],
                        ),
                      ),
          ),
        ),
      );
}
