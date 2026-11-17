/* One photo refresh owner. Keep the last decoded photo until a candidate succeeds. */
(function () {
    'use strict';
    function milliseconds(value, fallback) {
        value = Number(value);
        return isFinite(value) && value > 0 ? Math.max(100, Math.min(value, 2147483647)) : fallback;
    }
    function PhotoFrame(options) {
        this.options = options;
        this.generation = 0;
        this.attempt = null;
        this.timer = null;
        this.stopped = false;
    }
    PhotoFrame.prototype.cancel = function () {
        var attempt = this.attempt;
        this.attempt = null;
        if (!attempt) { return; }
        clearTimeout(attempt.timer);
        attempt.xhr.onreadystatechange = null;
        attempt.xhr.abort();
        if (attempt.image) {
            attempt.image.onload = attempt.image.onerror = null;
            attempt.image.src = '';
        }
    };
    PhotoFrame.prototype.stop = function () {
        this.stopped = true;
        this.generation += 1;
        clearTimeout(this.timer);
        this.cancel();
    };
    PhotoFrame.prototype.refresh = function (retry) {
        if (this.stopped) { return; }
        retry = retry || 0;
        clearTimeout(this.timer);
        this.cancel();
        var self = this;
        var generation = ++this.generation;
        var attempt = {xhr: new XMLHttpRequest(), image: null, timer: null};
        this.attempt = attempt;
        function current() {
            return !self.stopped && self.generation === generation && self.attempt === attempt;
        }
        function schedule(delay, nextRetry) {
            self.timer = setTimeout(function () { self.refresh(nextRetry); }, delay);
        }
        function fail() {
            if (!current()) { return; }
            self.cancel();
            document.getElementById('photo-status').textContent = 'Unable to refresh photo; retrying.';
            schedule(retry < self.options.retries ? self.options.retryDelay : self.options.interval,
                     retry < self.options.retries ? retry + 1 : 0);
        }
        function swap(data) {
            if (!current()) { return; }
            var candidate = attempt.image;
            candidate.onload = candidate.onerror = null;
            attempt.image = null; // Cancellation must never clear the visible photo.
            var old = document.getElementById('frame-photo');
            candidate.id = 'frame-photo';
            candidate.className = 'fullScreenPhoto';
            candidate.alt = 'Random photo';
            old.parentNode.replaceChild(candidate, old);
            document.getElementById('creation-date').textContent = data.creation_date || 'Unknown';
            document.getElementById('creation-time').textContent = data.creation_time || '';
            document.getElementById('photo-status').textContent = '';
            document.querySelector('.loading-placeholder').classList.add('hidden');
            self.cancel();
            schedule(self.options.interval, 0);
        }
        // Deadline covers both metadata and image/decode, on every retry.
        attempt.timer = setTimeout(fail, this.options.timeout);
        attempt.xhr.open('GET', '/random-picture/metadata', true);
        attempt.xhr.onreadystatechange = function () {
            if (!current() || attempt.xhr.readyState !== 4) { return; }
            if (attempt.xhr.status !== 200) { fail(); return; }
            var data;
            try {
                data = JSON.parse(attempt.xhr.responseText);
                if (!/^\/random-picture\/snapshots\/[a-f0-9]{32}$/.test(data.picture_url)) {
                    throw new Error('No snapshot');
                }
            } catch (error) { fail(); return; }
            var candidate = new Image();
            attempt.image = candidate;
            candidate.onerror = fail;
            candidate.onload = function () {
                if (!current()) { return; }
                if (candidate.decode) {
                    candidate.decode().then(function () { swap(data); }, fail);
                } else if (candidate.naturalWidth > 0) {
                    swap(data);
                } else { fail(); }
            };
            candidate.src = data.picture_url;
        };
        attempt.xhr.send();
    };
    window.PhotoFrame = PhotoFrame;
    document.addEventListener('DOMContentLoaded', function () {
        var body = document.body;
        var frame = new PhotoFrame({
            interval: milliseconds(body.dataset.refreshMs, 30000),
            timeout: milliseconds(body.dataset.timeoutMs, 15000),
            retryDelay: milliseconds(body.dataset.retryMs, 2000), retries: 3
        });
        window.photoFrame = frame;
        frame.refresh();
        var weatherTimer = null;
        var weatherRequest = null;
        var stopped = false;
        function refreshWeather() {
            if (stopped) { return; }
            var xhr = new XMLHttpRequest();
            weatherRequest = xhr;
            xhr.open('GET', '/weather/cached-overlay', true);
            xhr.timeout = 8000;
            xhr.onload = function () {
                if (!stopped && xhr.status === 200) {
                    // Same-origin, server-rendered Jinja fragment; EXIF is never HTML.
                    document.getElementById('weather-overlay').innerHTML = xhr.responseText;
                }
            };
            xhr.onloadend = function () {
                if (!stopped) { weatherTimer = setTimeout(refreshWeather, milliseconds(body.dataset.weatherMs, 60000)); }
            };
            xhr.send();
        }
        refreshWeather();
        window.addEventListener('pageshow', function (event) {
            if (event.persisted && stopped) {
                stopped = false;
                frame.stopped = false;
                frame.refresh();
                refreshWeather();
            }
        });
        window.addEventListener('pagehide', function () {
            stopped = true;
            frame.stop();
            clearTimeout(weatherTimer);
            if (weatherRequest) { weatherRequest.abort(); }
        });
    });
}());
