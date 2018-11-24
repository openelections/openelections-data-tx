class UnknownRaceNameError(Exception):
    """Error raised when a lookup by race name fails."""
    pass


class SheetsError(Exception):
    """Error raised when there's an issue updating google sheets."""
    pass


class PageDownloadError(Exception):
    """Error raised when we fail to download a page."""
    pass


class EmptyPageContentError(Exception):
    """Error raised when content for a page is empty"""
    pass


class SoSParsingError(Exception):
    """Parent class for errors when parsing pages."""


class PageStructureError(SoSParsingError):
    """Error raised when the page structure is different than expected"""
    pass


class PageDataError(SoSParsingError):
    """Error raised when the data on the page is different than expected"""
    pass


class NoDemCandidateError(SoSParsingError):
    """Error raised when a candidate page is parsed but it doesn't include a DEM candidate."""
    pass
