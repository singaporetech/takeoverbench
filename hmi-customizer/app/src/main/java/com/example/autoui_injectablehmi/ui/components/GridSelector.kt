package com.example.autoui_injectablehmi.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.ui.unit.dp

@Composable
fun GridSelector(
    cols: Int = 8,
    rows: Int = 6,
    startCol: Int,
    endCol: Int,
    startRow: Int,
    endRow: Int,
    onSelectionChanged: (sc: Int, ec: Int, sr: Int, er: Int) -> Unit
) {
    // Temporary states while the user's finger is dragging on the screen
    var dragStartCell by remember { mutableStateOf<Pair<Int, Int>?>(null) }
    var dragEndCell by remember { mutableStateOf<Pair<Int, Int>?>(null) }

    Canvas(
        modifier = Modifier
            .fillMaxWidth()
            .aspectRatio(cols.toFloat() / rows.toFloat())
            .clipToBounds()
            .background(Color(0xFFE8F0FE)) // Light blue background
            .border(2.dp, Color(0xFF1976D2), RoundedCornerShape(8.dp))

            // Handle Single Taps
            .pointerInput(Unit) {
                detectTapGestures { offset ->
                    val col = (offset.x / (size.width / cols)).toInt().coerceIn(0, cols - 1)
                    val row = (offset.y / (size.height / rows)).toInt().coerceIn(0, rows - 1)
                    onSelectionChanged(col, col, row, row)
                }
            }
            // Handle Drag & Drop to select multiple cells
            .pointerInput(Unit) {
                detectDragGestures(
                    onDragStart = { offset ->
                        val col = (offset.x / (size.width / cols)).toInt().coerceIn(0, cols - 1)
                        val row = (offset.y / (size.height / rows)).toInt().coerceIn(0, rows - 1)
                        dragStartCell = col to row
                        dragEndCell = col to row
                    },
                    onDrag = { change, _ ->
                        val col = (change.position.x / (size.width / cols)).toInt().coerceIn(0, cols - 1)
                        val row = (change.position.y / (size.height / rows)).toInt().coerceIn(0, rows - 1)
                        dragEndCell = col to row
                    },
                    onDragEnd = {
                        if (dragStartCell != null && dragEndCell != null) {
                            val sc = minOf(dragStartCell!!.first, dragEndCell!!.first)
                            val ec = maxOf(dragStartCell!!.first, dragEndCell!!.first)
                            val sr = minOf(dragStartCell!!.second, dragEndCell!!.second)
                            val er = maxOf(dragStartCell!!.second, dragEndCell!!.second)
                            onSelectionChanged(sc, ec, sr, er)
                        }
                        dragStartCell = null
                        dragEndCell = null
                    }
                )
            }
    ) {
        // Because of the dynamic height, cells will become perfect rectangles
        // mapped to the tablet's actual screen ratio.
        val cellWidth = size.width / cols
        val cellHeight = size.height / rows

        // 1. Draw Grid Lines
        for (i in 1 until cols) {
            drawLine(Color(0xFFBBDEFB), Offset(i * cellWidth, 0f), Offset(i * cellWidth, size.height), 2.dp.toPx())
        }
        for (i in 1 until rows) {
            drawLine(Color(0xFFBBDEFB), Offset(0f, i * cellHeight), Offset(size.width, i * cellHeight), 2.dp.toPx())
        }

        // 2. Determine which cells to highlight (Active drag vs Saved state)
        val activeStartCol = dragStartCell?.let { minOf(it.first, dragEndCell!!.first) } ?: startCol
        val activeEndCol = dragStartCell?.let { maxOf(it.first, dragEndCell!!.first) } ?: endCol
        val activeStartRow = dragStartCell?.let { minOf(it.second, dragEndCell!!.second) } ?: startRow
        val activeEndRow = dragStartCell?.let { maxOf(it.second, dragEndCell!!.second) } ?: endRow

        val rectX = activeStartCol * cellWidth
        val rectY = activeStartRow * cellHeight
        val rectW = (activeEndCol - activeStartCol + 1) * cellWidth
        val rectH = (activeEndRow - activeStartRow + 1) * cellHeight

        // 3. Draw the Dragged Area (Red Banner preview)
        drawRect(
            color = Color(0x80D32F2F), // Semi-transparent Red fill
            topLeft = Offset(rectX, rectY),
            size = Size(rectW, rectH)
        )
        drawRect(
            color = Color.Red, // Solid Red border
            topLeft = Offset(rectX, rectY),
            size = Size(rectW, rectH),
            style = Stroke(width = 3.dp.toPx())
        )
    }
}