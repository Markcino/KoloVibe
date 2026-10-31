import '../core/presentation/feature_repository.dart';
import 'service_repositories.dart';

class AppDependencies {
  const AppDependencies.unavailable()
      : services = const ServiceRepositories.unavailable();
  const AppDependencies({required this.services});
  final ServiceRepositories services;
  FeatureRepository get repository => RepositoryDispatcher(services);
}
