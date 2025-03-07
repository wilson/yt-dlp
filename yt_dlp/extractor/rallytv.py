import re

from .common import InfoExtractor
from ..utils import ExtractorError


class RallyTVIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?rally\.tv/video/(?P<id>[\w-]+)'
    _TESTS = [{
        'url': 'https://www.rally.tv/video/3f435f44-b6e2-50de-923d-d8cd8311ddef',
        'info_dict': {
            'id': '3f435f44-b6e2-50de-923d-d8cd8311ddef',
            'ext': 'mp4',
            'title': re.compile(r'.+'),
        },
        'params': {
            'skip_download': True,
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        self.to_screen(f'Extracting video with ID: {video_id}')

        # Download webpage for title extraction
        webpage = self._download_webpage(url, video_id)
        title = self._html_search_regex(
            r'<title>([^<]+)</title>', webpage, 'title', default=f'Rally.TV Video {video_id}',
        )
        title = re.sub(r'\s*\|\s*Rally\.TV.*$', '', title)

        # Use the direct master playlist URL
        formats = []
        master_url = f'https://dms.redbull.tv/v5/destination/rallytv/{video_id}/personal_computer/http/us/en_US/playlist.m3u8'
        self.to_screen(f'Attempting to fetch master playlist: {master_url}')

        headers = self.geo_verification_headers()
        headers.update({
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://www.rally.tv',
            'Referer': 'https://www.rally.tv/',
            'Connection': 'keep-alive',
        })

        try:
            # Extract formats from the master playlist
            master_formats = self._extract_m3u8_formats(
                master_url, video_id, 'mp4',
                entry_protocol='m3u8_native',
                headers=headers,
                fatal=True)  # Fatal since this is our primary approach

            if master_formats:
                self.to_screen(f'Successfully extracted {len(master_formats)} formats from master playlist')
                formats.extend(master_formats)
        except Exception as e:
            raise ExtractorError(f'Failed to extract video formats: {e}')

        if not formats:
            raise ExtractorError('Could not extract any video formats.')

        return {
            'id': video_id,
            'title': title,
            'formats': formats,
        }
