package com.example.autoui_injectablehmi.ui.screens
import com.example.autoui_injectablehmi.R

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import com.example.autoui_injectablehmi.ui.components.AlertBanner
import com.example.autoui_injectablehmi.viewmodel.DashboardViewModel
import androidx.compose.foundation.Image
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource

@Composable
fun DashboardScreen(
    viewModel: DashboardViewModel,
    modifier: Modifier = Modifier
) {
    // Observe the state flows from the ViewModel
    val isAlertVisible by viewModel.isAlertVisible.collectAsState()
    val bannerSettings by viewModel.bannerSettings.collectAsState()

    // A Box allows the banner to overlay on top of the base dashboard
    Box(
        modifier = modifier.fillMaxSize()
    ) {
        // Base Dashboard UI
        Image(
            painter = painterResource(
                id = R.drawable.home
            ),
            contentDescription = null,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.FillBounds
        )

        // Overlay the Takeover Request Banner if triggered
        if (isAlertVisible) {
            AlertBanner(
                settings = bannerSettings,
                modifier = Modifier.matchParentSize()
            )
        }
    }
}