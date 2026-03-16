import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:geolocator/geolocator.dart';

class LocationService {
  static const Duration _cacheTtl = Duration(seconds: 30);

  Position? _cachedPosition;
  DateTime? _cachedAt;

  Future<Map<String, dynamic>?> buildLocationContextPayload() async {
    final position = await _getCurrentPosition();
    if (position == null) {
      return null;
    }

    return {
      'type': 'device_location',
      'latitude': position.latitude,
      'longitude': position.longitude,
      'accuracy_meters': position.accuracy,
      'captured_at': position.timestamp.toIso8601String(),
    };
  }

  Future<Position?> _getCurrentPosition() async {
    try {
      if (_cachedPosition != null &&
          _cachedAt != null &&
          DateTime.now().difference(_cachedAt!) < _cacheTtl) {
        return _cachedPosition;
      }

      final servicesEnabled = await Geolocator.isLocationServiceEnabled();
      if (!servicesEnabled) {
        return _getLastKnownPosition();
      }

      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        return _getLastKnownPosition();
      }

      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.medium,
          timeLimit: Duration(seconds: 4),
        ),
      );
      _cachedPosition = position;
      _cachedAt = DateTime.now();
      return position;
    } on MissingPluginException catch (error) {
      debugPrint('LocationService: geolocator plugin unavailable: $error');
      return null;
    } catch (_) {
      return _getLastKnownPosition();
    }
  }

  Future<Position?> _getLastKnownPosition() async {
    try {
      final position = await Geolocator.getLastKnownPosition();
      if (position != null) {
        _cachedPosition = position;
        _cachedAt = DateTime.now();
      }
      return position;
    } on MissingPluginException catch (error) {
      debugPrint(
        'LocationService: geolocator last-known plugin unavailable: $error',
      );
      return null;
    } catch (_) {
      return null;
    }
  }
}

final locationServiceProvider = Provider<LocationService>((ref) {
  return LocationService();
});
