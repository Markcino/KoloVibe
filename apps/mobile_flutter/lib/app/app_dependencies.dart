import '../core/presentation/feature_repository.dart';
import 'service_repositories.dart';

class AppDependencies {
  const AppDependencies.unavailable()
      : demo = false,
        services = const ServiceRepositories.unavailable();

  // A release cannot opt into simulated service responses.
  final bool demo;
  final ServiceRepositories services;
  FeatureRepository get repository => RepositoryDispatcher(services);
}
