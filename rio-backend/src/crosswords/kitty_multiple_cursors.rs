use crate::config::colors::ColorRgb;
use crate::crosswords::pos::{Column, Line};

#[derive(Debug, Copy, Clone, Eq, PartialEq)]
pub enum KittyExtraCursorShape {
    Block,
    Beam,
    Underline,
    FollowMain,
}

impl KittyExtraCursorShape {
    pub fn from_protocol_code(code: u16) -> Option<Option<Self>> {
        match code {
            0 => Some(None),
            1 => Some(Some(Self::Block)),
            2 => Some(Some(Self::Beam)),
            3 => Some(Some(Self::Underline)),
            29 => Some(Some(Self::FollowMain)),
            _ => None,
        }
    }

    pub fn protocol_code(self) -> u16 {
        match self {
            Self::Block => 1,
            Self::Beam => 2,
            Self::Underline => 3,
            Self::FollowMain => 29,
        }
    }
}

#[derive(Debug, Copy, Clone, Eq, PartialEq, Default)]
pub enum KittyExtraCursorColor {
    #[default]
    Unset,
    Special,
    Rgb(ColorRgb),
    Indexed(u8),
}

impl KittyExtraCursorColor {
    pub fn from_subparams(params: &[u16]) -> Option<Self> {
        match params {
            [0] => Some(Self::Unset),
            [1] => Some(Self::Special),
            [2, r, g, b] if *r <= 255 && *g <= 255 && *b <= 255 => {
                Some(Self::Rgb(ColorRgb {
                    r: *r as u8,
                    g: *g as u8,
                    b: *b as u8,
                }))
            }
            [5, index] if *index <= 255 => Some(Self::Indexed(*index as u8)),
            _ => None,
        }
    }

    pub fn query_payload(self, which: u16) -> String {
        match self {
            Self::Unset => format!("{which}:0"),
            Self::Special => format!("{which}:1"),
            Self::Rgb(color) => format!("{which}:2:{}:{}:{}", color.r, color.g, color.b),
            Self::Indexed(index) => format!("{which}:5:{index}"),
        }
    }
}

#[derive(Debug, Copy, Clone, Eq, PartialEq, Default)]
pub struct KittyExtraCursorColors {
    pub text: KittyExtraCursorColor,
    pub cursor: KittyExtraCursorColor,
}

#[derive(Debug, Copy, Clone, Eq, PartialEq)]
pub struct KittyExtraCursor {
    pub row: Line,
    pub col: Column,
    pub shape: KittyExtraCursorShape,
}
