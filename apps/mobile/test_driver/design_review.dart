import 'dart:io';
import 'package:integration_test/integration_test_driver_extended.dart';

Future<void> main() async {
  final directory = Directory('build/runtime-ui-review')
    ..createSync(recursive: true);
  await integrationDriver(
    onScreenshot: (name, bytes, [arguments]) async {
      await File('${directory.path}/$name.png').writeAsBytes(bytes);
      return true;
    },
    responseDataCallback: (data) async {
      final coverage = data?['coverage'];
      if (coverage is! String) {
        throw StateError('Simulator run did not return route coverage');
      }
      await File('${directory.path}/coverage.csv').writeAsString(coverage);
    },
  );
}
