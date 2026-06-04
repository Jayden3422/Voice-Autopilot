import request from './request.js'

export function getAPI(url, params) {
  return request({ method: 'get', url, params })
}

export function postAPI(url, data) {
  return request({ method: 'post', url, data })
}

export function putAPI(url, data) {
  return request({ method: 'put', url, data })
}

export function deleteListAPI(url, params) {
  return request({ method: 'delete', url, params })
}
