package com.example.coma_link

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.example.coma_link.ui.ComaLinkApp
import com.example.coma_link.ui.theme.Coma_linkTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            Coma_linkTheme {
                ComaLinkApp()
            }
        }
    }
}