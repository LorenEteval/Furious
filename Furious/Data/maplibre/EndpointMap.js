(() => {
  'use strict';

  let bridge = null;
  let map = null;
  let marker = null;
  let state = null;
  let appliedRevision = -1;
  let activeStyleKey = '';
  let initialReadyReported = false;
  const loadingOverlay = document.getElementById('endpoint-loading-overlay');
  const loadingText = document.getElementById('endpoint-loading-text');

  const nameField = [
    'case',
    ['all', ['has', 'name:latin'], ['has', 'name:nonlatin']],
    ['concat', ['get', 'name:latin'], '\n', ['get', 'name:nonlatin']],
    [
      'coalesce',
      ['get', 'name_en'],
      ['get', 'name'],
      ['get', 'name:latin'],
      '',
    ],
  ];

  const MAP_PALETTES = {
    dark: {
      land: '#151a22',
      landcover: '#19231f',
      landuse: '#1a2028',
      water: '#182734',
      roadMinor: '#303a46',
      roadMajor: '#465363',
      building: '#202731',
      waterLabel: '#8fa6b8',
    },
    light: {
      land: '#f7f9fc',
      landcover: '#eaf0e9',
      landuse: '#edf1f5',
      water: '#e2ebf2',
      roadMinor: '#dce4ed',
      roadMajor: '#becad8',
      building: '#e4e9ef',
      waterLabel: '#607d94',
    },
  };

  const createPalette = (themeState) => {
    const darkMode = Boolean(themeState.darkMode);
    const mapPalette = MAP_PALETTES[darkMode ? 'dark' : 'light'];

    return {
      ...mapPalette,
      background: themeState.surfaceColor || (darkMode ? '#11161d' : '#f8fafd'),
      boundary: themeState.borderColor || (darkMode ? '#2a3340' : '#d9e1ec'),
      label: themeState.textColor || (darkMode ? '#e7ecf4' : '#172033'),
      labelMuted: themeState.mutedTextColor || (darkMode ? '#9aa7b8' : '#5e6b80'),
      halo: themeState.surfaceColor || (darkMode ? '#11161d' : '#f8fafd'),
      poi: themeState.mutedTextColor || (darkMode ? '#9aa7b8' : '#5e6b80'),
    };
  };

  const createStyle = (themeState) => {
    const colors = createPalette(themeState);

    return {
      version: 8,
      glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
      sources: {
        openmaptiles: {
          type: 'vector',
          url: 'https://tiles.openfreemap.org/planet',
          attribution: '<a href="https://openfreemap.org/">OpenFreeMap</a> ' +
            '<a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        },
      },
      layers: [
        {
          id: 'background',
          type: 'background',
          paint: {'background-color': colors.background},
        },
        {
          id: 'land',
          type: 'fill',
          source: 'openmaptiles',
          'source-layer': 'landcover',
          paint: {'fill-color': colors.land},
        },
        {
          id: 'landcover',
          type: 'fill',
          source: 'openmaptiles',
          'source-layer': 'landcover',
          paint: {
            'fill-color': colors.landcover,
            'fill-opacity': 0.3,
          },
        },
        {
          id: 'landuse',
          type: 'fill',
          source: 'openmaptiles',
          'source-layer': 'landuse',
          paint: {
            'fill-color': colors.landuse,
            'fill-opacity': 0.32,
          },
        },
        {
          id: 'water',
          type: 'fill',
          source: 'openmaptiles',
          'source-layer': 'water',
          paint: {'fill-color': colors.water},
        },
        {
          id: 'boundary',
          type: 'line',
          source: 'openmaptiles',
          'source-layer': 'boundary',
          paint: {
            'line-color': colors.boundary,
            'line-width': 0.8,
            'line-opacity': 0.52,
          },
        },
        {
          id: 'transportation',
          type: 'line',
          source: 'openmaptiles',
          'source-layer': 'transportation',
          minzoom: 5,
          paint: {
            'line-color': colors.roadMinor,
            'line-width': 0.8,
            'line-opacity': 0.46,
          },
        },
        {
          id: 'transportation-major',
          type: 'line',
          source: 'openmaptiles',
          'source-layer': 'transportation',
          minzoom: 6,
          filter: [
            'match',
            ['get', 'class'],
            ['motorway', 'trunk', 'primary', 'secondary', 'tertiary'],
            true,
            false,
          ],
          paint: {
            'line-color': colors.roadMajor,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              6,
              0.8,
              14,
              2.4,
            ],
            'line-opacity': 0.72,
          },
        },
        {
          id: 'building',
          type: 'fill',
          source: 'openmaptiles',
          'source-layer': 'building',
          minzoom: 14,
          paint: {
            'fill-color': colors.building,
            'fill-opacity': 0.42,
          },
        },
        {
          id: 'water-name',
          type: 'symbol',
          source: 'openmaptiles',
          'source-layer': 'water_name',
          minzoom: 3,
          layout: {
            'symbol-placement': 'point',
            'text-field': nameField,
            'text-font': ['Noto Sans Italic'],
            'text-size': [
              'interpolate',
              ['linear'],
              ['zoom'],
              3,
              10,
              12,
              14,
            ],
            'text-max-width': 8,
          },
          paint: {
            'text-color': colors.waterLabel,
            'text-halo-color': colors.halo,
            'text-halo-width': 1,
            'text-opacity': 0.76,
          },
        },
        {
          id: 'road-name-major',
          type: 'symbol',
          source: 'openmaptiles',
          'source-layer': 'transportation_name',
          minzoom: 11,
          filter: [
            'match',
            ['get', 'class'],
            ['motorway', 'trunk', 'primary', 'secondary', 'tertiary'],
            true,
            false,
          ],
          layout: {
            'symbol-placement': 'line',
            'symbol-spacing': 300,
            'text-field': nameField,
            'text-font': ['Noto Sans Regular'],
            'text-size': [
              'interpolate',
              ['linear'],
              ['zoom'],
              11,
              10,
              16,
              13,
            ],
          },
          paint: {
            'text-color': colors.labelMuted,
            'text-halo-color': colors.halo,
            'text-halo-width': 1,
            'text-opacity': 0.72,
          },
        },
        {
          id: 'road-name-minor',
          type: 'symbol',
          source: 'openmaptiles',
          'source-layer': 'transportation_name',
          minzoom: 15,
          filter: [
            'match',
            ['get', 'class'],
            ['minor', 'service', 'track', 'path'],
            true,
            false,
          ],
          layout: {
            'symbol-placement': 'line',
            'symbol-spacing': 260,
            'text-field': nameField,
            'text-font': ['Noto Sans Regular'],
            'text-size': 11,
          },
          paint: {
            'text-color': colors.labelMuted,
            'text-halo-color': colors.halo,
            'text-halo-width': 1,
            'text-opacity': 0.58,
          },
        },
        {
          id: 'place-country',
          type: 'symbol',
          source: 'openmaptiles',
          'source-layer': 'place',
          minzoom: 2,
          maxzoom: 9,
          filter: ['==', ['get', 'class'], 'country'],
          layout: {
            'text-field': nameField,
            'text-font': ['Noto Sans Bold'],
            'text-size': [
              'interpolate',
              ['linear'],
              ['zoom'],
              2,
              10,
              7,
              16,
            ],
            'text-max-width': 7,
          },
          paint: {
            'text-color': colors.label,
            'text-halo-color': colors.halo,
            'text-halo-width': 1.2,
          },
        },
        {
          id: 'place-state',
          type: 'symbol',
          source: 'openmaptiles',
          'source-layer': 'place',
          minzoom: 4,
          maxzoom: 10,
          filter: ['==', ['get', 'class'], 'state'],
          layout: {
            'text-field': nameField,
            'text-font': ['Noto Sans Italic'],
            'text-size': 11,
            'text-letter-spacing': 0.08,
            'text-max-width': 8,
          },
          paint: {
            'text-color': colors.labelMuted,
            'text-halo-color': colors.halo,
            'text-halo-width': 1,
            'text-opacity': 0.72,
          },
        },
        {
          id: 'place-city',
          type: 'symbol',
          source: 'openmaptiles',
          'source-layer': 'place',
          minzoom: 3,
          filter: [
            'match',
            ['get', 'class'],
            ['city', 'town', 'village'],
            true,
            false,
          ],
          layout: {
            'text-field': nameField,
            'text-font': ['Noto Sans Regular'],
            'text-size': [
              'interpolate',
              ['linear'],
              ['zoom'],
              4,
              11,
              12,
              15,
            ],
            'text-max-width': 8,
            'text-variable-anchor': ['top', 'bottom', 'left', 'right'],
            'text-radial-offset': 0.4,
          },
          paint: {
            'text-color': colors.label,
            'text-halo-color': colors.halo,
            'text-halo-width': 1.2,
          },
        },
        {
          id: 'poi-name',
          type: 'symbol',
          source: 'openmaptiles',
          'source-layer': 'poi',
          minzoom: 16,
          layout: {
            'text-field': nameField,
            'text-font': ['Noto Sans Regular'],
            'text-size': 10,
            'text-max-width': 9,
          },
          paint: {
            'text-color': colors.poi,
            'text-halo-color': colors.halo,
            'text-halo-width': 1,
            'text-opacity': 0.58,
          },
        },
      ],
    };
  };

  const coordinate = () => {
    if (!state || !state.markerVisible) {
      return null;
    }

    const longitude = Number(state.markerLongitude);
    const latitude = Number(state.markerLatitude);
    if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
      return null;
    }

    return [longitude, latitude];
  };

  const applyLoadingState = () => {
    const loading = Boolean(state && state.loading);
    loadingOverlay.dataset.visible = String(loading);
    loadingOverlay.setAttribute('aria-hidden', String(!loading));
    loadingText.textContent = loading && state.loadingText
      ? state.loadingText
      : '';
  };

  const applyThemeState = () => {
    if (!state) {
      return;
    }

    document.documentElement.dataset.theme = state.darkMode
      ? 'dark'
      : 'light';

    const properties = {
      '--endpoint-accent': state.accentColor,
      '--endpoint-surface': state.surfaceColor,
      '--endpoint-border': state.borderColor,
      '--endpoint-text': state.textColor,
      '--endpoint-text-muted': state.mutedTextColor,
      '--endpoint-font-family': JSON.stringify(state.fontFamily || 'sans-serif'),
      '--endpoint-font-size': `${state.fontPointSize || 11}pt`,
    };

    for (const [name, value] of Object.entries(properties)) {
      if (value) {
        document.documentElement.style.setProperty(name, value);
      }
    }
  };

  const styleKey = () => JSON.stringify([
    Boolean(state.darkMode),
    state.surfaceColor,
    state.borderColor,
    state.textColor,
    state.mutedTextColor,
  ]);

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
    const markerCoordinate = coordinate();
    if (!map || !markerCoordinate) {
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
      .setLngLat(markerCoordinate)
      .addTo(map);
  };

  const applyState = () => {
    applyLoadingState();
    applyThemeState();

    if (!state) {
      return;
    }

    if (!map) {
      return;
    }

    const nextStyleKey = styleKey();
    if (nextStyleKey !== activeStyleKey) {
      activeStyleKey = nextStyleKey;
      const nextStyle = createStyle(state);
      map.setStyle(nextStyle);
    }

    const nextCoordinate = coordinate();
    if (nextCoordinate && state.viewRevision !== appliedRevision) {
      appliedRevision = state.viewRevision;
      map.jumpTo({
        center: nextCoordinate,
        zoom: state.defaultGeographicZoom,
      });
    }

    ensureMarker();
    map.resize();
  };

  const createMap = () => {
    const initialCoordinate = coordinate();
    if (map || !initialCoordinate) {
      return;
    }

    activeStyleKey = styleKey();
    map = new maplibregl.Map({
      container: 'map',
      style: createStyle(state),
      center: initialCoordinate,
      zoom: state.defaultGeographicZoom,
      minZoom: 2,
      maxZoom: 18,
      maxTileCacheSize: 64,
      canvasContextAttributes: {
        antialias: false,
        powerPreference: 'low-power',
      },
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

  window.endpointMap = {
    setState(nextState) {
      state = nextState;
      applyThemeState();
      applyLoadingState();
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
