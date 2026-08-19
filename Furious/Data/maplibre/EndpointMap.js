(() => {
  'use strict';

  let bridge = null;
  let map = null;
  let marker = null;
  let state = null;
  let appliedRevision = -1;
  let activeStyle = '';
  let initialReadyReported = false;

  const reportError = (event) => {
    const message = event && event.error && event.error.message
      ? event.error.message
      : 'The map provider could not be loaded.';
    if (bridge) {
      bridge.failed(String(message));
    }
  };

  const reportReady = () => {
    if (!initialReadyReported && bridge) {
      initialReadyReported = true;
      bridge.ready();
    }
  };

  const ensureMarker = () => {
    if (!map || !state || !state.markerVisible) {
      if (marker) {
        marker.remove();
        marker = null;
      }
      return;
    }

    if (!marker) {
      const element = document.createElement('div');
      element.className = 'endpoint-marker';
      marker = new maplibregl.Marker({element, anchor: 'center'});
    }

    marker
      .setLngLat([state.markerLongitude, state.markerLatitude])
      .addTo(map);
  };

  const applyState = () => {
    if (!map || !state) {
      return;
    }

    document.documentElement.dataset.theme = state.darkMode
      ? 'dark'
      : 'light';

    document.documentElement.style.setProperty(
      '--endpoint-accent',
      state.accentColor
    );
    const nextStyle = state.darkMode
      ? state.darkStyleUrl
      : state.lightStyleUrl;
    if (nextStyle !== activeStyle) {
      activeStyle = nextStyle;
      map.setStyle(nextStyle);
    }

    if (state.viewRevision !== appliedRevision) {
      appliedRevision = state.viewRevision;
      map.jumpTo({
        center: [state.markerLongitude, state.markerLatitude],
        zoom: state.defaultGeographicZoom,
      });
    }

    ensureMarker();
    map.resize();
  };

  const createMap = () => {
    if (map || !state) {
      return;
    }

    activeStyle = state.darkMode
      ? state.darkStyleUrl
      : state.lightStyleUrl;
    map = new maplibregl.Map({
      container: 'map',
      style: activeStyle,
      center: [state.markerLongitude, state.markerLatitude],
      zoom: state.defaultGeographicZoom,
      minZoom: 2,
      maxZoom: 18,
      attributionControl: true,
      cooperativeGestures: false,
      fadeDuration: 0,
    });
    map.on('error', reportError);
    map.once('load', () => {
      ensureMarker();
      reportReady();
    });
    applyState();
  };

  window.furiousEndpointMap = {
    setState(nextState) {
      state = nextState;
      createMap();
      applyState();
    },
  };

  document.addEventListener('click', (event) => {
    const anchor = event.target.closest('a[href]');
    if (!anchor || !bridge) {
      return;
    }

    event.preventDefault();
    bridge.openExternal(anchor.href);
  }, true);

  new QWebChannel(qt.webChannelTransport, (channel) => {
    bridge = channel.objects.endpointMapBridge;
    createMap();
  });
})();
