"""Marketing Scoring Module.

This module provides the MarketingScorer class for calculating customer
intention scores, segmentation, and recommended actions.
"""

from typing import Protocol, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

import pandas as pd
import structlog

from ..config.constants import MARKETING_THRESHOLDS
from ..core.exceptions import DataProcessingError

logger = structlog.get_logger(__name__)


class ScoringStrategy(Protocol):
    """Protocol for scoring strategies."""
    
    def calculate(self, row: pd.Series) -> int:
        """Calculate score for a single row.
        
        Args:
            row: DataFrame row with customer data
            
        Returns:
            Score value
        """
        ...


@dataclass
class ScoringThresholds:
    """Configuration for scoring thresholds."""
    high_value: float = 1_000_000
    medium_value: float = 300_000
    high_frequency: int = 5
    medium_frequency: int = 3
    recent_days: int = 7
    medium_days: int = 30
    high_cart_value: float = 300_000
    medium_cart_value: float = 100_000


class DefaultScoringStrategy:
    """Default implementation of scoring strategy.
    
    Calculates score based on:
    - Historical value (LTV): 0-30 points
    - Frequency: 0-30 points
    - Recency: 0-20 points
    - Cart value: 0-20 points
    """
    
    def __init__(self, thresholds: ScoringThresholds = None) -> None:
        """Initialize strategy with thresholds.
        
        Args:
            thresholds: Scoring thresholds configuration
        """
        self.thresholds = thresholds or ScoringThresholds()
    
    def calculate(self, row: pd.Series) -> int:
        """Calculate intention score.
        
        Args:
            row: Customer data row
            
        Returns:
            Total score (0-100)
        """
        score = 0
        
        # Extract values safely
        ltv = float(row.get("LTV_Gasto_Total", 0) or 0)
        frecuencia = int(row.get("Frecuencia", 0) or 0)
        recencia = float(row.get("Recencia_Dias", 9999) or 9999)
        subtotal = float(row.get("Subtotal", 0) or 0)
        
        # Historical value score (0-30)
        if ltv > self.thresholds.high_value:
            score += 30
        elif ltv > self.thresholds.medium_value:
            score += 20
        elif ltv > 0:
            score += 10
        
        # Frequency score (0-30)
        if frecuencia >= self.thresholds.high_frequency:
            score += 30
        elif frecuencia >= self.thresholds.medium_frequency:
            score += 20
        elif frecuencia >= 1:
            score += 10
        
        # Recency score (0-20)
        if recencia <= self.thresholds.recent_days:
            score += 20
        elif recencia <= self.thresholds.medium_days:
            score += 10
        
        # Cart value score (0-20)
        if subtotal >= self.thresholds.high_cart_value:
            score += 20
        elif subtotal >= self.thresholds.medium_cart_value:
            score += 10
        
        return score


class MarketingScorer:
    """Calculate marketing scores and segment customers.
    
    This class handles the complete scoring pipeline including:
    - Score calculation
    - Segmentation
    - Customer classification
    - Action recommendations
    
    Example:
        >>> scorer = MarketingScorer()
        >>> df_scored = scorer.score(df_customers)
        >>> df_with_actions = scorer.add_recommendations(df_scored)
    """
    
    # Segment thresholds
    HIGH_THRESHOLD = 70
    MEDIUM_THRESHOLD = 50
    
    # Customer type thresholds
    VIP_LTV_THRESHOLD = 1_000_000
    VIP_FREQUENCY_THRESHOLD = 5
    RECURRENT_THRESHOLD = 2
    
    def __init__(self, strategy: ScoringStrategy = None) -> None:
        """Initialize the marketing scorer.
        
        Args:
            strategy: Scoring strategy to use (default: DefaultScoringStrategy)
        """
        self.strategy = strategy or DefaultScoringStrategy()
        logger.info("marketing_scorer_initialized")
    
    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate scores for all customers.
        
        Args:
            df: Customer DataFrame
            
        Returns:
            DataFrame with added Score_Intencion column
            
        Raises:
            DataProcessingError: If scoring fails
        """
        try:
            logger.info("calculating_scores", rows=len(df))
            
            df = df.copy()
            df["Score_Intencion"] = df.apply(self.strategy.calculate, axis=1)
            
            logger.info("scores_calculated")
            return df
            
        except Exception as e:
            logger.error("scoring_failed", error=str(e))
            raise DataProcessingError(
                f"Failed to calculate scores: {e}",
                operation="score"
            )
    
    def segment(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add segment classification based on score.
        
        Args:
            df: DataFrame with Score_Intencion column
            
        Returns:
            DataFrame with added Segmento column
        """
        logger.debug("segmenting_customers")
        
        def get_segment(score: int) -> str:
            if score >= self.HIGH_THRESHOLD:
                return "Alta"
            elif score >= self.MEDIUM_THRESHOLD:
                return "Media"
            return "Baja"
        
        df = df.copy()
        df["Segmento"] = df["Score_Intencion"].apply(get_segment)
        
        logger.debug("segmentation_complete")
        return df
    
    def add_recommendations(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add action recommendations based on segment.
        
        Args:
            df: DataFrame with Segmento column
            
        Returns:
            DataFrame with added Accion_Sugerida column
        """
        logger.debug("adding_recommendations")
        
        def get_action(segment: str) -> str:
            actions = {
                "Alta": "WhatsApp + Cupón personalizado",
                "Media": "Email remarketing",
                "Baja": "Automatización suave"
            }
            return actions.get(segment, "Automatización suave")
        
        df = df.copy()
        df["Accion_Sugerida"] = df["Segmento"].apply(get_action)
        
        logger.debug("recommendations_added")
        return df
    
    def classify_customers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify customers as VIP, Recurrent, or New.
        
        Customers with Invoice A are automatically classified as VIP.
        
        Args:
            df: Customer DataFrame
            
        Returns:
            DataFrame with added Tipo_Cliente column
        """
        logger.debug("classifying_customers")
        
        def get_customer_type(row: pd.Series) -> str:
            # Check for Invoice A
            tiene_factura_a = str(row.get("Tiene_Factura_A", "No")).strip().lower()
            if tiene_factura_a == "sí" or tiene_factura_a == "si":
                return "VIP"
            
            # Traditional criteria
            ltv = float(row.get("LTV_Gasto_Total", 0) or 0)
            frecuencia = int(row.get("Frecuencia", 0) or 0)
            
            if ltv >= self.VIP_LTV_THRESHOLD or frecuencia >= self.VIP_FREQUENCY_THRESHOLD:
                return "VIP"
            elif frecuencia >= self.RECURRENT_THRESHOLD:
                return "Recurrente"
            return "Nuevo"
        
        df = df.copy()
        df["Tipo_Cliente"] = df.apply(get_customer_type, axis=1)
        
        logger.debug("classification_complete")
        return df
    
    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """Execute the complete scoring pipeline.
        
        This method runs all scoring operations in sequence:
        1. Calculate scores
        2. Segment customers
        3. Add recommendations
        4. Classify customer types
        
        Args:
            df: Customer DataFrame
            
        Returns:
            Fully processed DataFrame
        """
        logger.info("starting_marketing_scoring_pipeline")
        
        df = self.score(df)
        df = self.segment(df)
        df = self.add_recommendations(df)
        df = self.classify_customers(df)
        
        logger.info("marketing_scoring_pipeline_complete")
        return df
