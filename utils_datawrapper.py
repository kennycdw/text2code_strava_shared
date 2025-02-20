import requests
import json
from typing import Tuple, Optional, Dict, Any
from loguru import logger

class DataWrapper:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.datawrapper.de/v3"
        self.headers = {"Authorization": f"Bearer {self.api_token}"}

    def _make_request(self, method: str, endpoint: str, data: Any = None) -> Tuple[bool, dict]:
        """
        Make HTTP request to Datawrapper API
        Returns: (success, response_data)
        """
        try:
            url = f"{self.base_url}/{endpoint}"
            if method.lower() == "get":
                response = requests.get(url, headers=self.headers)
            elif method.lower() == "post":
                response = requests.post(url, headers=self.headers)
            elif method.lower() == "put":
                response = requests.put(url, headers=self.headers, data=data)
            
            response.raise_for_status()  # Raise exception for bad status codes
            return True, response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Datawrapper API request failed: {str(e)}")
            return False, {}
        
    def create_chart(self) -> Tuple[bool, str, str]:
        """Create empty chart and return (success, chart_id, status)"""
        success, data = self._make_request("post", "charts")
        if success and data:
            try:
                chart_id = data.get('id')
                if chart_id:
                    return True, chart_id, "Chart created successfully"
            except (KeyError, AttributeError) as e:
                logger.error(f"Failed to parse chart creation response: {e}")
        
        return False, '', "Failed to create chart"

    def upload_data(self, chart_id: str, web_link: str) -> Tuple[bool, bool]:
        """Upload data to chart from web link or CSV string"""
        try:
            payload = {
                'metadata': {'data': {'transpose': False, 'external-data': web_link}},
                'externalData': web_link
            }
            success, response = self._make_request("put", f"charts/{chart_id}", data=json.dumps(payload))
        
            if success:
                return True, "Data uploaded successfully"
            logger.error(f"Failed to upload data: {response}")
            return False, "Failed to upload data"
            
        except Exception as e:
            logger.error(f"Error uploading data: {str(e)}")
            return False, f"Error: {str(e)}"

    def configure_chart(self, chart_id: str, title: str, chart_type: str, metadata: dict) -> Tuple[bool, str]:
        """Configure chart properties"""
        try:
            current_config = {}
            current_config['title'] = title
            current_config['type'] = chart_type

            # Update metadata 
            if 'metadata' not in current_config:
                current_config['metadata'] = {}

            # Handle external data logic (configurations within metadata[data])
            if 'external-data' in metadata:
                if 'data' not in current_config['metadata']:
                    current_config['metadata']['data'] = {}
                current_config['metadata']['data']['external-data'] = metadata['external-data']
                current_config['metadata']['data']['upload-method'] = 'external-data'
                current_config['metadata']['data']['use-datawrapper-cdn'] = False

            # Handle all configurations from visualization and describe
            if 'visualize' in metadata:
                current_config['metadata']['visualize'] = metadata['visualize']
            if 'describe' in metadata:
                current_config['metadata']['describe'] = metadata['describe']
            if 'publish' in metadata:
                current_config['metadata']['publish'] = metadata['publish']

            # Update chart
            #logger.info(f"Current config: {current_config}")
            success, response = self._make_request("put", f"charts/{chart_id}", data=json.dumps(current_config))
            
            if success:
                return True, "Chart configured successfully"
            return False, "Failed to update chart configuration"

        except Exception as e:
            logger.error(f"Error configuring chart: {str(e)}")
            return False, f"Error: {str(e)}"

    def publish_chart(self, chart_id: str, metadata: dict = None) -> Tuple[bool, str]:
        """Publish chart and return (success, embed_code)"""
        current_config = {}
        if 'publish' in metadata:
            current_config = metadata['publish']
        success, response = self._make_request("post", f"charts/{chart_id}/publish", data=json.dumps(current_config))
        
        if success:
            embed_code_responsive = response['data']['metadata']['publish']['embed-codes']['embed-method-responsive']
            embed_code_web_component = response['data']['metadata']['publish']['embed-codes']['embed-method-web-component']
            return True, embed_code_responsive, embed_code_web_component
        return False, ''

    def create_and_publish_chart(self, title: str, chart_type: str, web_link: str,
                                 describe_settings: dict = None,
                                 visualization_settings: dict = None,
                                 publish_settings: dict = None) -> Tuple[bool, str, str]:
        """
        Create, configure, and publish a chart in one go
        
        Args:
            title: Chart title
            chart_type: Type of chart (e.g., 'd3-bars-split')
            web_link: URL for external data
            visualization_settings: Dictionary of visualization settings
            
        Returns:
            Tuple[bool, str, str]: (success, chart_id, embed_code/error_message)
        """
        try:
            # Create empty chart
            success, chart_id, message = self.create_chart()
            if not success:
                return False, "", f"Failed to create chart: {message}"

            # Upload data
            success, message = self.upload_data(chart_id=chart_id, web_link=web_link)
            if not success:
                return False, chart_id, f"Failed to upload data: {message}"

            # Configure chart
            metadata = {'external-data': web_link}
            if describe_settings:
                metadata['describe'] = describe_settings
            # Add visualization settings if provided
            if visualization_settings:
                metadata['visualize'] = visualization_settings
            if publish_settings:
                metadata['publish'] = publish_settings

            success, message = self.configure_chart(
                chart_id=chart_id,
                title=title,
                chart_type=chart_type,
                metadata=metadata
            )
            if not success:
                return False, chart_id, f"Failed to configure chart: {message}"

            # Publish chart
            success, embed_code_responsive, embed_code_web_component = self.publish_chart(chart_id=chart_id, metadata= metadata)
            if not success:
                return False, chart_id, "Failed to publish chart"

            return True, chart_id, embed_code_responsive, embed_code_web_component

        except Exception as e:
            logger.error(f"Error creating chart: {str(e)}")
            return False, "", str(e)


    def get_chart_metadata(self, chart_id: str) -> Tuple[bool, dict]:
        """
        Retrieve complete chart metadata
        Args:
            chart_id: The chart ID
        Returns:
            Tuple[bool, dict]: (success, response_data)
        """
        try:
            success, response = self._make_request("get", f"charts/{chart_id}")
            if success:
                #logger.info(f"Successfully retrieved metadata for chart {chart_id}")
                return True, response
            
            logger.error(f"Failed to retrieve metadata for chart {chart_id}")
            return False, {}
            
        except Exception as e:
            logger.error(f"Error retrieving chart metadata: {str(e)}")
            return False, {}
