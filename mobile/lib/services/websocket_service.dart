import 'dart:async';
import 'dart:convert';


import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class WsMessage {
  final String type;
  final String? text;
  final String? role;
  final Uint8List? audioData;
  final String? mimeType;
  final String? toolName;
  final Map<String, dynamic>? toolArgs;
  final String? error;

  WsMessage({
    required this.type,
    this.text,
    this.role,
    this.audioData,
    this.mimeType,
    this.toolName,
    this.toolArgs,
    this.error,
  });

  factory WsMessage.fromJson(Map<String, dynamic> json) {
    Uint8List? audio;
    if (json['data'] != null && json['type'] == 'audio') {
      audio = base64Decode(json['data'] as String);
    }
    return WsMessage(
      type: json['type'] as String? ?? 'unknown',
      text: json['text'] as String?,
      role: json['role'] as String?,
      audioData: audio,
      mimeType: json['mime_type'] as String?,
      toolName: json['name'] as String?,
      toolArgs: json['args'] as Map<String, dynamic>?,
      error: json['message'] as String?,
    );
  }
}

enum WsConnectionState { disconnected, connecting, connected, error }

class WebSocketService {
  WebSocketChannel? _channel;
  final _messageController = StreamController<WsMessage>.broadcast();
  final _stateController =
      StreamController<WsConnectionState>.broadcast();
  WsConnectionState _state = WsConnectionState.disconnected;
  Timer? _reconnectTimer;
  int _reconnectAttempt = 0;
  String? _url;

  Stream<WsMessage> get messages => _messageController.stream;
  Stream<WsConnectionState> get stateStream => _stateController.stream;
  WsConnectionState get state => _state;

  void connect(String url) {
    _url = url;
    _reconnectAttempt = 0;
    _doConnect();
  }

  void _doConnect() {
    if (_url == null) return;
    _setState(WsConnectionState.connecting);
    debugPrint('WS: Connecting to $_url');

    try {
      _channel = WebSocketChannel.connect(Uri.parse(_url!));
      _channel!.ready.then((_) {
        debugPrint('WS: Connected successfully');
        _setState(WsConnectionState.connected);
        _reconnectAttempt = 0;

        _channel!.stream.listen(
          (data) {
            if (data is String) {
              try {
                final json = jsonDecode(data) as Map<String, dynamic>;
                final preview = (json['text'] ?? json['name'] ?? '').toString();
                debugPrint('WS: Received [${json['type']}] ${preview.length > 60 ? preview.substring(0, 60) : preview}');
                _messageController.add(WsMessage.fromJson(json));
              } catch (e) {
                debugPrint('WS: Parse error: $e');
              }
            } else {
              debugPrint('WS: Received non-string data: ${data.runtimeType}');
            }
          },
          onDone: () {
            debugPrint('WS: Connection closed by server');
            _onDisconnected();
          },
          onError: (e) {
            debugPrint('WS: Stream error: $e');
            _setState(WsConnectionState.error);
            _scheduleReconnect();
          },
        );
      }).catchError((e) {
        debugPrint('WS: Connection failed: $e');
        _setState(WsConnectionState.error);
        _scheduleReconnect();
      });
    } catch (e) {
      debugPrint('WS: Connect exception: $e');
      _setState(WsConnectionState.error);
      _scheduleReconnect();
    }
  }

  void _onDisconnected() {
    _setState(WsConnectionState.disconnected);
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    if (_url == null) return;
    final delay = Duration(
      seconds: [1, 2, 4, 8, 15, 30][_reconnectAttempt.clamp(0, 5)],
    );
    _reconnectAttempt++;
    _reconnectTimer = Timer(delay, _doConnect);
  }

  void sendAudio(Uint8List pcmData) {
    if (_state != WsConnectionState.connected) return;
    final msg = jsonEncode({
      'type': 'audio',
      'data': base64Encode(pcmData),
    });
    _channel?.sink.add(msg);
  }

  void sendText(String text) {
    if (_state != WsConnectionState.connected) {
      debugPrint('WS: Cannot send text, not connected (state=$_state)');
      return;
    }
    debugPrint('WS: Sending text: ${text.length > 60 ? text.substring(0, 60) : text}');
    _channel?.sink.add(jsonEncode({'type': 'text', 'text': text}));
    _channel?.sink.add(jsonEncode({'type': 'end_turn'}));
  }

  void disconnect() {
    _url = null;
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
    _setState(WsConnectionState.disconnected);
  }

  void _setState(WsConnectionState s) {
    _state = s;
    _stateController.add(s);
  }

  void dispose() {
    disconnect();
    _messageController.close();
    _stateController.close();
  }
}

final webSocketServiceProvider = Provider<WebSocketService>((ref) {
  final service = WebSocketService();
  ref.onDispose(() => service.dispose());
  return service;
});
