package com.example.coma_link.ui.util

/**
 * 判断 slotStart-slotEnd 是否覆盖目标 slotId。
 */
fun slotRangeOverlap(startId: String, endId: String, targetId: String, order: List<String>): Boolean {
    val start = order.indexOf(startId)
    val end = order.indexOf(endId)
    val target = order.indexOf(targetId)
    if (start == -1 || end == -1 || target == -1) return false
    val (s, e) = if (start <= end) start to end else end to start
    return target in s..e
}

