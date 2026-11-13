import 'package:flutter/foundation.dart';
import '../../core/network/api_client.dart';
import 'live_points_repository.dart';

enum PointsPhase { loading, failed, ready }

/// Which slice of the ledger a screen shows.
enum PointsView { overview, confirmed, pending, history, withheld, adjustments }

/// Loads the server-owned balance and pages the server-owned ledger.
///
/// Nothing here awards, sums or estimates points. Totals come from the
/// balance read; rows come from the entries read. The only client-side
/// selection is [PointsView.withheld], because the server has no `withheld`
/// filter: those rows are picked out of the `all` pages by their server status.
class PointsController extends ChangeNotifier {
  PointsController(this._repository, this.view,
      {PointsFilter filter = PointsFilter.all})
      : _filter = view == PointsView.history ? filter : _serverFilter(view);

  /// A withheld view may fetch this many pages in one action looking for rows.
  static const maxAutoPages = 5;

  final LivePointsRepository _repository;
  final PointsView view;

  PointsPhase phase = PointsPhase.loading;
  Object? error;
  PointsBalance? balance;

  /// Set when a pull-to-refresh failed but earlier data is still shown.
  Object? refreshError;

  /// Set when "load more" failed; the rows already shown are kept.
  Object? moreError;
  bool loadingMore = false;
  bool refreshing = false;
  String? _cursor;
  final List<PointsEntry> _entries = [];
  PointsFilter _filter;
  int _generation = 0;
  bool _disposed = false;

  PointsFilter get filter => _filter;
  bool get hasMore => _cursor != null;

  /// Rows to show for this view, in the order the server returned them.
  List<PointsEntry> get entries => view == PointsView.withheld
      ? _entries.where((entry) => entry.isWithheld).toList(growable: false)
      : List.unmodifiable(_entries);

  /// True once at least one ledger row of any kind has been read.
  bool get hasAnyEntries => _entries.isNotEmpty;

  static PointsFilter _serverFilter(PointsView view) => switch (view) {
        PointsView.confirmed => PointsFilter.confirmed,
        PointsView.pending => PointsFilter.pending,
        PointsView.adjustments => PointsFilter.adjustments,
        _ => PointsFilter.all,
      };

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  void _emit() {
    if (!_disposed) notifyListeners();
  }

  /// A fixed failure for responses that cannot be trusted.
  static const _unreadable =
      ApiFailure(503, 'Your Lone Stars could not be read. Try again.');

  /// Initial load, and the retry from the failed state.
  Future<void> load() => _load(keepData: false);

  /// Pull-to-refresh: a failure keeps what is already on screen.
  Future<void> refresh() => _load(keepData: balance != null);

  Future<void> _load({required bool keepData}) async {
    final generation = ++_generation;
    if (keepData) {
      refreshing = true;
      refreshError = null;
    } else {
      phase = PointsPhase.loading;
      error = null;
    }
    moreError = null;
    loadingMore = false;
    _emit();
    try {
      final current = await _repository.balance();
      final page = await _repository.entries(filter: _filter);
      if (_disposed || generation != _generation) return;
      _checkOwner(current, page.items);
      balance = current;
      _entries
        ..clear()
        ..addAll(page.items);
      _cursor = page.nextCursor;
      phase = PointsPhase.ready;
      refreshError = null;
      refreshing = false;
      _emit();
      if (view == PointsView.withheld) await _fillWithheld(generation, 0);
      return;
    } on ApiFailure catch (failure) {
      _fail(generation, failure, keepData);
    } on FormatException {
      _fail(generation, _unreadable, keepData);
    }
  }

  void _fail(int generation, Object failure, bool keepData) {
    if (_disposed || generation != _generation) return;
    refreshing = false;
    if (keepData) {
      refreshError = failure;
    } else {
      error = failure;
      phase = PointsPhase.failed;
    }
    _emit();
  }

  void _checkOwner(PointsBalance current, List<PointsEntry> items) {
    if (items.any((item) => item.creatorId != current.creatorId)) {
      throw const FormatException('Mismatched points owner');
    }
  }

  /// Switches the history filter and reloads from the first page.
  Future<void> setFilter(PointsFilter next) async {
    if (view != PointsView.history || next == _filter) return;
    _filter = next;
    await _load(keepData: false);
  }

  /// Fetches the next page. One request at a time; a failure keeps the rows.
  Future<void> loadMore() async {
    final cursor = _cursor;
    if (loadingMore ||
        cursor == null ||
        phase != PointsPhase.ready ||
        balance == null) {
      return;
    }
    final generation = _generation;
    final shown = entries.length;
    loadingMore = true;
    moreError = null;
    _emit();
    try {
      await _appendPage(generation, cursor);
      if (view == PointsView.withheld) await _fillWithheld(generation, shown);
    } on ApiFailure catch (failure) {
      if (!_disposed && generation == _generation) moreError = failure;
    } on FormatException {
      if (!_disposed && generation == _generation) moreError = _unreadable;
    } finally {
      if (!_disposed && generation == _generation) {
        loadingMore = false;
        _emit();
      }
    }
  }

  Future<void> _appendPage(int generation, String cursor) async {
    final page = await _repository.entries(cursor: cursor, filter: _filter);
    if (_disposed || generation != _generation) return;
    final known = _entries.map((entry) => entry.id).toSet();
    _checkOwner(balance!, page.items);
    if (page.items.any((entry) => known.contains(entry.id))) {
      throw const FormatException('Repeated points rows');
    }
    _entries.addAll(page.items);
    _cursor = page.nextCursor;
    _emit();
  }

  /// The server cannot filter to withheld rows, so keep reading the `all`
  /// pages (bounded) until a withheld row beyond the [shown] ones is visible
  /// or the ledger ends. A later "load more" continues from the same cursor.
  Future<void> _fillWithheld(int generation, int shown) async {
    var pages = 0;
    while (!_disposed &&
        generation == _generation &&
        entries.length <= shown &&
        _cursor != null &&
        pages < maxAutoPages) {
      pages++;
      if (!loadingMore) {
        loadingMore = true;
        _emit();
      }
      try {
        await _appendPage(generation, _cursor!);
      } on ApiFailure catch (failure) {
        if (!_disposed && generation == _generation) moreError = failure;
        break;
      } on FormatException {
        if (!_disposed && generation == _generation) moreError = _unreadable;
        break;
      }
    }
    if (!_disposed && generation == _generation && loadingMore) {
      loadingMore = false;
      _emit();
    }
  }
}

enum PointsEntryPhase { loading, failed, ready }

/// Loads one owner-only ledger entry (M-065) and, best effort, its source
/// video title. The title is a convenience: any failure leaves it blank.
class PointsEntryController extends ChangeNotifier {
  PointsEntryController(this._repository, this.entryId, {this.videoTitle});

  final LivePointsRepository _repository;
  final String entryId;

  /// Resolves a video id to a title; null result or throw means "unknown".
  final Future<String?> Function(String videoId)? videoTitle;

  PointsEntryPhase phase = PointsEntryPhase.loading;
  Object? error;
  PointsEntry? entry;
  String? sourceTitle;
  bool _disposed = false;
  int _generation = 0;

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  void _emit() {
    if (!_disposed) notifyListeners();
  }

  Future<void> load() async {
    final generation = ++_generation;
    phase = PointsEntryPhase.loading;
    error = null;
    _emit();
    try {
      final value = await _repository.entry(entryId);
      if (_disposed || generation != _generation) return;
      entry = value;
      phase = PointsEntryPhase.ready;
      _emit();
      await _loadTitle(generation, value.videoId);
    } on ApiFailure catch (failure) {
      _fail(generation, failure);
    } on FormatException {
      _fail(generation,
          const ApiFailure(503, 'This entry could not be read. Try again.'));
    }
  }

  void _fail(int generation, Object failure) {
    if (_disposed || generation != _generation) return;
    error = failure;
    phase = PointsEntryPhase.failed;
    _emit();
  }

  Future<void> _loadTitle(int generation, String? videoId) async {
    final resolve = videoTitle;
    if (resolve == null || videoId == null) return;
    try {
      final title = await resolve(videoId);
      if (_disposed || generation != _generation) return;
      sourceTitle = title;
      _emit();
    } catch (_) {
      // The title is optional; the entry itself is still correct.
    }
  }
}
