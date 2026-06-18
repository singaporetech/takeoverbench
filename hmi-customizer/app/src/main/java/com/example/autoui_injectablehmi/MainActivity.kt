package com.example.autoui_injectablehmi

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import com.example.autoui_injectablehmi.ui.screens.DashboardScreen
import com.example.autoui_injectablehmi.ui.screens.SettingsScreen
import com.example.autoui_injectablehmi.ui.theme.Autoui_injectablehmiTheme
import com.example.autoui_injectablehmi.viewmodel.DashboardViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 1. Initialize the ViewModel
        val viewModel = ViewModelProvider(this)[DashboardViewModel::class.java]

        lifecycleScope.launch(Dispatchers.IO) {
            MQTTManager.connect()

            // 2. Pass the ViewModel into the Notification Service
            NotificationService.initialise(viewModel)
        }

        enableEdgeToEdge()

        setContent {
            Autoui_injectablehmiTheme {
                // 3. Launch the App Navigator
                AppNavigator(viewModel = viewModel)
            }
        }
    }
}

@Composable
fun AppNavigator(viewModel: DashboardViewModel) {
    // Simple state to remember which screen you are on (Dashboard or Settings)
    var currentScreen by remember { mutableStateOf("Dashboard") }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    icon = { Icon(Icons.Filled.Home, contentDescription = "Dashboard") },
                    label = { Text("Dashboard") },
                    selected = currentScreen == "Dashboard",
                    onClick = { currentScreen = "Dashboard" }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Filled.Settings, contentDescription = "Settings") },
                    label = { Text("Settings") },
                    selected = currentScreen == "Settings",
                    onClick = { currentScreen = "Settings" }
                )
            }
        }
    ) { innerPadding ->
        // This Box swaps out the screens based on the bottom bar selection
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
        ) {
            if (currentScreen == "Dashboard") {
                // Calls the isolated DashboardScreen component
                DashboardScreen(viewModel = viewModel)
            } else {
                // Calls the isolated SettingsScreen component
                SettingsScreen(viewModel = viewModel)
            }
        }
    }
}