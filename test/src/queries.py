def get_metadata_request_from_id() -> str:
    return """
    query($id: ID!) {
        metadataRequest(id: $id) {
            id
            datasetAddress
            algorithmAddress
            requester
        }
    }
    """
