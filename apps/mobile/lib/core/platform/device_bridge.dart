import 'package:flutter/services.dart';

class AppVersion {
  const AppVersion(this.version, this.build);
  final String version;
  final String build;
}

/// Native capabilities used by designs: system share sheet, app settings,
/// installed version, and opening approved HTTPS pages outside the app.
abstract class DeviceBridge {
  const DeviceBridge();
  Future<bool> share(String text);
  Future<bool> openAppSettings();
  Future<AppVersion?> appVersion();
  Future<bool> openUrl(Uri url);
}

class PlatformDeviceBridge extends DeviceBridge {
  const PlatformDeviceBridge();
  static const _channel = MethodChannel('kolovibe/device');

  Future<T?> _call<T>(String method, [Map<String, Object?>? arguments]) async {
    try {
      return await _channel.invokeMethod<T>(method, arguments);
    } on MissingPluginException {
      return null;
    } on PlatformException {
      return null;
    }
  }

  @override
  Future<bool> share(String text) async {
    if (text.isEmpty || text.length > 2048) return false;
    return await _call<bool>('share', {'text': text}) ?? false;
  }

  @override
  Future<bool> openAppSettings() async =>
      await _call<bool>('openSettings') ?? false;

  @override
  Future<AppVersion?> appVersion() async {
    final value = await _call<Map<Object?, Object?>>('appVersion');
    final version = value?['version'], build = value?['build'];
    if (version is! String || build is! String || version.isEmpty) return null;
    return AppVersion(version, build);
  }

  @override
  Future<bool> openUrl(Uri url) async {
    if (url.scheme != 'https' || url.host.isEmpty || url.userInfo.isNotEmpty) {
      return false;
    }
    return await _call<bool>('openUrl', {'url': url.toString()}) ?? false;
  }
}
