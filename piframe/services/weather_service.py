"""
Weather service for PiFrame application.
Handles weather API calls, caching, and chart generation.
"""

import io
import json
import os
import time
from typing import Optional, Dict, Any, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config.settings import Config
from ..models.cache import CacheManager, get_cache_manager
from ..utils.logging import LoggerMixin, log_performance


FigureCanvas = None
Figure = None
plt = None


def _load_matplotlib():
    """Load matplotlib only when chart rendering is requested."""
    global FigureCanvas, Figure, plt

    if FigureCanvas is None or Figure is None or plt is None:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as matplotlib_pyplot
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure as MatplotlibFigure

        FigureCanvas = FigureCanvasAgg
        Figure = MatplotlibFigure
        plt = matplotlib_pyplot

    return FigureCanvas, Figure, plt


class WeatherService(LoggerMixin):
    """Service for weather data retrieval and chart generation."""
    
    def __init__(self, config: Config, cache_manager: Optional[CacheManager] = None):
        """
        Initialize weather service.
        
        Args:
            config: Application configuration
            cache_manager: Cache manager instance
        """
        self.config = config
        self.cache_manager = cache_manager or get_cache_manager(config)
        self._session = None
        
    @property
    def session(self) -> requests.Session:
        """Get or create requests session with proper configuration."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                'User-Agent': 'PiFrame/0.2.0'
            })
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
            
        return self._session
    
    @log_performance
    def get_current_weather(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get current weather data with caching.
        
        Args:
            force_refresh: Skip cache and fetch fresh data
            
        Returns:
            Weather data dictionary or None if unavailable
        """
        if not self.config.weather_api_key:
            self.logger.warning("Weather API key not configured")
            return None
        
        cache_key = f"current_{self.config.weather_location}"
        
        # Try cache first unless force refresh
        if not force_refresh:
            cached_data = self.cache_manager.get('weather', cache_key)
            if cached_data is not None:
                self.logger.debug("Using cached weather data")
                return cached_data
        
        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?appid={self.config.weather_api_key}"
                f"&q={self.config.weather_location}"
            )
            
            self.logger.info(f"Fetching weather data for {self.config.weather_location}")
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            weather_data = response.json()
            
            # Cache the result
            self.cache_manager.set('weather', cache_key, weather_data)
            
            self.logger.info("Weather data fetched and cached successfully")
            return weather_data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Weather API request failed: {e}")
            # Return cached data if available, even if expired
            cached_data = self.cache_manager.get('weather', cache_key)
            if cached_data is not None:
                self.logger.info("Using expired cached weather data as fallback")
                return cached_data
            return None
        except (ValueError, KeyError) as e:
            self.logger.error(f"Invalid weather API response: {e}")
            return None
    
    @log_performance
    def get_forecast(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get weather forecast data with caching.
        
        Args:
            force_refresh: Skip cache and fetch fresh data
            
        Returns:
            Forecast data dictionary or None if unavailable
        """
        cache_key = f"forecast_{self.config.weather_location}"
        
        # Try cache first unless force refresh
        if not force_refresh:
            cached_data = self.cache_manager.get('forecast', cache_key)
            if cached_data is not None:
                self.logger.debug("Using cached forecast data")
                return cached_data
        
        # Try file fallback first
        if os.path.exists(self.config.weather_file_fallback):
            try:
                with open(self.config.weather_file_fallback, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.cache_manager.set('forecast', cache_key, data)
                    self.logger.info("Loaded forecast data from file fallback")
                    return data
            except (json.JSONDecodeError, FileNotFoundError) as e:
                self.logger.warning(f"Could not load forecast from file: {e}")
        
        # Fetch from API
        if not self.config.weather_api_key:
            self.logger.warning("Weather API key not configured")
            return None
        
        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/forecast"
                f"?appid={self.config.weather_api_key}"
                f"&lat={self.config.weather_lat}"
                f"&lon={self.config.weather_lon}"
            )
            
            self.logger.info("Fetching forecast data from API")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            forecast_data = response.json()
            
            # Cache the result
            self.cache_manager.set('forecast', cache_key, forecast_data)
            
            self.logger.info("Forecast data fetched and cached successfully")
            return forecast_data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Forecast API request failed: {e}")
            # Return cached data if available
            cached_data = self.cache_manager.get('forecast', cache_key)
            if cached_data is not None:
                self.logger.info("Using expired cached forecast data as fallback")
                return cached_data
            return None
        except (ValueError, KeyError) as e:
            self.logger.error(f"Invalid forecast API response: {e}")
            return None
    
    def to_celsius(self, kelvin_temp: float) -> float:
        """Convert Kelvin to Celsius."""
        return round(kelvin_temp - 273.15, 1)
    
    def process_forecast_data(self, forecast_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process raw forecast data into display format.
        
        Args:
            forecast_data: Raw forecast data from API
            
        Returns:
            List of processed forecast items
        """
        if not forecast_data or 'list' not in forecast_data:
            return []
        
        result = []
        for item in forecast_data['list']:
            try:
                temp = self.to_celsius(item['main']['temp'])
                feels_like = self.to_celsius(item['main']['feels_like'])
                humidity = item['main']['humidity']
                weather = item['weather'][0]['main']
                dt = item['dt_txt']
                time_str = item['dt_txt'][11:16]  # HH:MM format
                icon_path = f"/static/images/{item['weather'][0]['icon']}@2x.gif"
                
                result.append({
                    'dt': dt,
                    'temp': temp,
                    'feels_like': feels_like,
                    'weather': weather,
                    'humidity': humidity,
                    'icon': icon_path,
                    'time': time_str,
                })
            except (KeyError, TypeError, ValueError) as e:
                self.logger.warning(f"Error processing forecast item: {e}")
                continue
        
        return result
    
    @log_performance
    def generate_forecast_chart(self, force_refresh: bool = False) -> Optional[bytes]:
        """
        Generate forecast chart as PNG bytes.
        
        Args:
            force_refresh: Skip cache and generate new chart
            
        Returns:
            PNG chart data as bytes or None if generation failed
        """
        cache_key = "forecast_chart"
        
        # Try cache first unless force refresh
        if not force_refresh:
            cached_chart = self.cache_manager.get('chart', cache_key)
            if cached_chart is not None:
                self.logger.debug("Using cached forecast chart")
                return cached_chart
        
        try:
            # Get forecast data
            forecast_data = self.get_forecast()
            if not forecast_data:
                self.logger.warning("No forecast data available for chart generation")
                return None
            
            forecast = self.process_forecast_data(forecast_data)
            if not forecast:
                self.logger.warning("No processed forecast data available")
                return None
            
            figure_canvas, _, pyplot = _load_matplotlib()

            # Create chart
            fig = self._create_forecast_figure(forecast)
            
            # Convert to PNG bytes
            output = io.BytesIO()
            figure_canvas(fig).print_png(output)
            chart_bytes = output.getvalue()
            
            # Close figure to free memory
            pyplot.close(fig)
            
            # Cache the result
            self.cache_manager.set('chart', cache_key, chart_bytes)
            
            self.logger.info("Forecast chart generated and cached")
            return chart_bytes
            
        except Exception as e:
            self.logger.error(f"Chart generation failed: {e}", exc_info=True)
            return None
    
    def _create_forecast_figure(self, forecast: List[Dict[str, Any]]) -> Any:
        """
        Create matplotlib figure for forecast data.
        
        Args:
            forecast: Processed forecast data
            
        Returns:
            Matplotlib figure
        """
        _, figure_class, _ = _load_matplotlib()

        # Use smaller figure size for better performance
        fig = figure_class(figsize=(8, 4), dpi=72)
        fig.patch.set_alpha(0.3)
        axis = fig.add_subplot(1, 1, 1, facecolor="none")
        
        if not forecast:
            return fig
        
        # dt format is "YYYY-MM-DD HH:MM:SS"
        # Extract "DD HH" as x-axis positions (unique per 3h interval)
        # Extract "HH" as human-readable tick labels
        xs = [f['dt'][8:13] for f in forecast]        # "DD HH" e.g. "25 14"
        xticks = [f['dt'][11:13] for f in forecast]   # "HH"    e.g. "14"
        temps = [f['temp'] for f in forecast]
        feels_like_temps = [f['feels_like'] for f in forecast]
        
        # Plot temperature lines
        axis.plot(xs, temps, color='red', label='Temperature', linewidth=1)
        axis.plot(xs, feels_like_temps, color='blue', label='Feels like', linewidth=1)
        
        # Configure chart
        axis.legend(loc='best', fontsize=8)
        axis.set_xticks(xs[::2])  # Show every other tick to avoid crowding
        axis.set_xticklabels(xticks[::2], fontsize=8)
        axis.tick_params(axis='x', rotation=45)
        
        # Add vertical lines at midnight boundaries ("DD 00")
        for val in xs:
            if val[3:] == '00':
                axis.axvline(x=val, color='black', alpha=0.3, linewidth=0.5)
        
        return fig
    
    def cleanup_expired_cache(self) -> None:
        """Clean up expired weather-related cache entries."""
        self.cache_manager.cleanup_all_expired()
        self.logger.debug("Weather cache cleanup completed")
    
    def close(self) -> None:
        """Close the service and clean up resources."""
        if self._session:
            try:
                self._session.close()
            except Exception as e:
                self.logger.warning(f"Error closing HTTP session: {e}")
            finally:
                self._session = None
        self.logger.info("Weather service closed")
        
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure resources are cleaned up."""
        self.close()
