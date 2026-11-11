import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiFailure implements Exception {
  const ApiFailure(this.status, this.message);
  final int status;
  final String message;
}

bool isApiId(Object? value) =>
    value is String &&
    RegExp(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
        .hasMatch(value);

/// Accepts only the configured gateway; credentials never appear in a URL.
class ApiClient {
  ApiClient(String baseUrl, {http.Client? client})
      : base = Uri.parse(baseUrl),
        _client = client ?? http.Client() {
    if (base.userInfo.isNotEmpty ||
        base.hasFragment ||
        base.hasQuery ||
        !base.path.endsWith('/api/v1') ||
        !(base.scheme == 'https' ||
            (kDebugMode &&
                base.scheme == 'http' &&
                base.host == '127.0.0.1'))) {
      throw ArgumentError('The gateway URL must be HTTPS or debug loopback');
    }
  }

  final Uri base;
  final http.Client _client;

  Future<Map<String, dynamic>> request(String path,
      {String method = 'GET',
      Map<String, Object?>? body,
      String? accessToken,
      String? idempotencyKey,
      Map<String, String>? query}) async {
    if (!path.startsWith('/') || path.contains('..') || path.contains('?')) {
      throw ArgumentError('Invalid API path');
    }
    if (idempotencyKey != null &&
        !RegExp(r'^[A-Za-z0-9_-]{16,128}$').hasMatch(idempotencyKey)) {
      throw ArgumentError('Invalid idempotency key');
    }
    final url = base.replace(path: '${base.path}$path', queryParameters: query);
    final request = http.Request(method, url)
      ..followRedirects = false
      ..headers['Accept'] = 'application/json';
    if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }
    if (accessToken != null) {
      request.headers['Authorization'] = 'Bearer $accessToken';
    }
    if (idempotencyKey != null) {
      request.headers['Idempotency-Key'] = idempotencyKey;
    }
    try {
      final streamed =
          await _client.send(request).timeout(const Duration(seconds: 8));
      if (streamed.contentLength != null && streamed.contentLength! > 65536) {
        throw const ApiFailure(503, 'The service response was too large.');
      }
      final bytes = <int>[];
      await for (final chunk
          in streamed.stream.timeout(const Duration(seconds: 8))) {
        bytes.addAll(chunk);
        if (bytes.length > 65536) {
          throw const ApiFailure(503, 'The service response was too large.');
        }
      }
      final decoded =
          bytes.isEmpty ? <String, dynamic>{} : jsonDecode(utf8.decode(bytes));
      if (decoded is! Map<String, dynamic>) throw const FormatException();
      if (streamed.statusCode >= 200 && streamed.statusCode < 300) {
        return decoded;
      }
      final detail = decoded['detail'];
      throw ApiFailure(
          streamed.statusCode,
          detail is String && detail.length <= 160
              ? detail
              : 'The request could not be completed.');
    } on ApiFailure {
      rethrow;
    } on TimeoutException {
      throw const ApiFailure(503, 'The service timed out. Please try again.');
    } on http.ClientException {
      throw const ApiFailure(
          503, 'The service is unavailable. Please try again.');
    } on FormatException {
      throw const ApiFailure(503, 'The service returned an invalid response.');
    }
  }
}
