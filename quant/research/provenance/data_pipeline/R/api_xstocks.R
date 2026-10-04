xstocks_multiplier_history <- function(symbol, network = "Ethereum") {
  url <- sprintf("https://api.xstocks.fi/api/v2/public/assets/%s/multiplier/history", symbol)
  req <- httr2::request(url) |> httr2::req_url_query(network = network) |> httr2::req_retry(max_tries = 4)
  resp <- httr2::req_perform(req)
  httr2::resp_body_json(resp, simplifyVector = FALSE)
}
