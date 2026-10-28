import 'package:flutter/foundation.dart';
import '../core/presentation/feature_repository.dart';
import 'service_repositories.dart';

class AppDependencies {
  const AppDependencies.unavailable()
      : demo = false,
        services = const ServiceRepositories.unavailable();
  AppDependencies.preview(this.services) : demo = true {
    if (kReleaseMode) {
      throw UnsupportedError('Demo mode is disabled in release builds.');
    }
  }
  final bool demo;
  final ServiceRepositories services;
  FeatureRepository get repository => RepositoryDispatcher(services);
}
