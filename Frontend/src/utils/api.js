import request from './request.js'

export function getAPI(url, params, config = {}) {
  return request({ method: 'get', url, params, ...config })
}

export function postAPI(url, data, config = {}) {
  return request({ method: 'post', url, data, ...config })
}

export function putAPI(url, data, config = {}) {
  return request({ method: 'put', url, data, ...config })
}

export function deleteListAPI(url, params, config = {}) {
  return request({ method: 'delete', url, params, ...config })
}
